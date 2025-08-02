"""Command execution service for running make commands with streaming output."""

import asyncio
import subprocess
import time
import os
import signal
from typing import Optional, Callable, Dict, Any, List, AsyncIterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ..models.command import Command


class ExecutionStatus(Enum):
    """Execution status types."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class ExecutionResult:
    """Result of command execution."""
    command: Command
    status: ExecutionStatus
    return_code: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    output_lines: List[str] = None
    error_lines: List[str] = None
    
    def __post_init__(self):
        if self.output_lines is None:
            self.output_lines = []
        if self.error_lines is None:
            self.error_lines = []
    
    @property
    def duration(self) -> float:
        """Get execution duration in seconds."""
        if self.end_time > 0:
            return self.end_time - self.start_time
        return time.time() - self.start_time if self.start_time > 0 else 0.0
    
    @property
    def success(self) -> bool:
        """Check if execution was successful."""
        return self.status == ExecutionStatus.SUCCESS and self.return_code == 0


@dataclass
class ExecutionProgress:
    """Progress information during execution."""
    command: Command
    status: ExecutionStatus
    output_line: Optional[str] = None
    error_line: Optional[str] = None
    progress_percent: Optional[float] = None
    elapsed_time: float = 0.0


class CommandExecutor:
    """Service for executing make commands with streaming output."""
    
    def __init__(self, makefile_dir: Optional[str] = None):
        """
        Initialize command executor.
        
        Args:
            makefile_dir: Directory containing Makefile (defaults to current directory)
        """
        self.makefile_dir = makefile_dir or self._find_makefile_dir()
        self.active_processes: Dict[str, subprocess.Popen] = {}
        self.execution_history: List[ExecutionResult] = []
        self.max_history = 50
        
        # Default timeout for commands (in seconds)
        self.default_timeout = 300  # 5 minutes
        
        # Command-specific timeouts
        self.command_timeouts = {
            "install": 600,      # 10 minutes for installs
            "deploy": 1800,      # 30 minutes for deploys
            "test": 300,         # 5 minutes for tests
            "clean": 300,        # 5 minutes for cleanup
        }
    
    def _find_makefile_dir(self) -> str:
        """Find directory containing Makefile."""
        current_dir = Path.cwd()
        
        # Look for Makefile in current directory and parents
        for path in [current_dir] + list(current_dir.parents):
            makefile_path = path / "Makefile"
            if makefile_path.exists():
                return str(path)
        
        # Default to current directory if no Makefile found
        return str(current_dir)
    
    async def execute_command(
        self,
        command: Command,
        progress_callback: Optional[Callable[[ExecutionProgress], None]] = None,
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        """
        Execute a make command with streaming output.
        
        Args:
            command: Command to execute
            progress_callback: Optional callback for progress updates
            timeout: Optional timeout in seconds
        
        Returns:
            ExecutionResult with execution details
        """
        # Create execution result
        result = ExecutionResult(
            command=command,
            status=ExecutionStatus.PENDING,
            start_time=time.time()
        )
        
        try:
            # Determine timeout
            exec_timeout = timeout or self._get_command_timeout(command)
            
            # Update status to running
            result.status = ExecutionStatus.RUNNING
            if progress_callback:
                progress = ExecutionProgress(
                    command=command,
                    status=ExecutionStatus.RUNNING,
                    elapsed_time=0.0
                )
                progress_callback(progress)
            
            # Execute command
            await self._execute_with_streaming(
                command, result, progress_callback, exec_timeout
            )
            
            # Determine final status
            if result.return_code == 0:
                result.status = ExecutionStatus.SUCCESS
            else:
                result.status = ExecutionStatus.FAILED
            
        except asyncio.TimeoutError:
            result.status = ExecutionStatus.TIMEOUT
            result.error_lines.append(f"Command timed out after {exec_timeout} seconds")
        except asyncio.CancelledError:
            result.status = ExecutionStatus.CANCELLED
            result.error_lines.append("Command execution was cancelled")
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error_lines.append(f"Execution error: {str(e)}")
        finally:
            result.end_time = time.time()
            
            # Final progress update
            if progress_callback:
                progress = ExecutionProgress(
                    command=command,
                    status=result.status,
                    elapsed_time=result.duration
                )
                progress_callback(progress)
            
            # Add to history
            self._add_to_history(result)
        
        return result
    
    async def _execute_with_streaming(
        self,
        command: Command,
        result: ExecutionResult,
        progress_callback: Optional[Callable[[ExecutionProgress], None]],
        timeout: int
    ) -> None:
        """Execute command with streaming output capture."""
        # Build command
        make_command = ["make", command.target]
        
        # Create process
        process = await asyncio.create_subprocess_exec(
            *make_command,
            cwd=self.makefile_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ.copy()
        )
        
        # Store process for potential cancellation
        process_id = f"{command.target}_{time.time()}"
        self.active_processes[process_id] = process
        
        try:
            # Stream output and errors concurrently
            tasks = [
                self._stream_output(process.stdout, result.output_lines, 
                                  command, progress_callback, False),
                self._stream_output(process.stderr, result.error_lines, 
                                  command, progress_callback, True)
            ]
            
            # Wait for process completion with timeout
            await asyncio.wait_for(
                asyncio.gather(*tasks, process.wait()),
                timeout=timeout
            )
            
            result.return_code = process.returncode
            
        except asyncio.TimeoutError:
            # Kill the process on timeout
            try:
                process.kill()
                await process.wait()
            except:
                pass
            raise
        finally:
            # Clean up process tracking
            if process_id in self.active_processes:
                del self.active_processes[process_id]
    
    async def _stream_output(
        self,
        stream: asyncio.StreamReader,
        output_lines: List[str],
        command: Command,
        progress_callback: Optional[Callable[[ExecutionProgress], None]],
        is_error: bool = False
    ) -> None:
        """Stream output from subprocess."""
        start_time = time.time()
        
        try:
            while True:
                line_bytes = await stream.readline()
                if not line_bytes:
                    break
                
                line = line_bytes.decode('utf-8', errors='replace').rstrip()
                output_lines.append(line)
                
                # Send progress update
                if progress_callback:
                    elapsed = time.time() - start_time
                    progress = ExecutionProgress(
                        command=command,
                        status=ExecutionStatus.RUNNING,
                        output_line=line if not is_error else None,
                        error_line=line if is_error else None,
                        elapsed_time=elapsed
                    )
                    progress_callback(progress)
                
        except Exception as e:
            error_msg = f"Stream error: {str(e)}"
            output_lines.append(error_msg)
    
    def _get_command_timeout(self, command: Command) -> int:
        """Get timeout for specific command."""
        # Check for specific command patterns
        target = command.target.lower()
        
        for pattern, timeout in self.command_timeouts.items():
            if pattern in target:
                return timeout
        
        return self.default_timeout
    
    def _add_to_history(self, result: ExecutionResult) -> None:
        """Add execution result to history."""
        self.execution_history.append(result)
        
        # Limit history size
        if len(self.execution_history) > self.max_history:
            self.execution_history = self.execution_history[-self.max_history:]
    
    async def cancel_command(self, command: Command) -> bool:
        """
        Cancel a running command.
        
        Args:
            command: Command to cancel
        
        Returns:
            True if command was cancelled, False if not found or already finished
        """
        # Find active process for this command
        process_to_cancel = None
        process_id_to_remove = None
        
        for process_id, process in self.active_processes.items():
            if command.target in process_id:
                process_to_cancel = process
                process_id_to_remove = process_id
                break
        
        if process_to_cancel and process_to_cancel.returncode is None:
            try:
                # Try graceful termination first
                process_to_cancel.terminate()
                
                # Wait a bit for graceful termination
                await asyncio.sleep(2)
                
                # Force kill if still running
                if process_to_cancel.returncode is None:
                    process_to_cancel.kill()
                
                # Wait for process to finish
                await process_to_cancel.wait()
                
                # Clean up tracking
                if process_id_to_remove in self.active_processes:
                    del self.active_processes[process_id_to_remove]
                
                return True
                
            except Exception:
                return False
        
        return False
    
    def get_running_commands(self) -> List[str]:
        """Get list of currently running command targets."""
        running = []
        for process_id, process in self.active_processes.items():
            if process.returncode is None:
                # Extract command target from process_id
                target = process_id.split('_')[0]
                running.append(target)
        return running
    
    def get_execution_history(self, limit: Optional[int] = None) -> List[ExecutionResult]:
        """
        Get execution history.
        
        Args:
            limit: Optional limit on number of results
        
        Returns:
            List of ExecutionResult objects
        """
        history = self.execution_history.copy()
        history.reverse()  # Most recent first
        
        if limit:
            history = history[:limit]
        
        return history
    
    def get_last_execution(self, command_target: Optional[str] = None) -> Optional[ExecutionResult]:
        """
        Get last execution result.
        
        Args:
            command_target: Optional target to filter by
        
        Returns:
            Last ExecutionResult or None
        """
        if not self.execution_history:
            return None
        
        if command_target:
            # Find last execution for specific target
            for result in reversed(self.execution_history):
                if result.command.target == command_target:
                    return result
            return None
        
        return self.execution_history[-1]
    
    async def test_command(self, command: Command) -> bool:
        """
        Test if a command can be executed (dry run).
        
        Args:
            command: Command to test
        
        Returns:
            True if command exists and can be executed
        """
        try:
            # Test with make -n (dry run)
            process = await asyncio.create_subprocess_exec(
                "make", "-n", command.target,
                cwd=self.makefile_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.wait()
            return process.returncode == 0
            
        except Exception:
            return False
    
    def is_command_running(self, command: Command) -> bool:
        """
        Check if a specific command is currently running.
        
        Args:
            command: Command to check
        
        Returns:
            True if command is running
        """
        return command.target in self.get_running_commands()
    
    def get_command_stats(self) -> Dict[str, Any]:
        """
        Get execution statistics.
        
        Returns:
            Dictionary with execution statistics
        """
        if not self.execution_history:
            return {
                "total_executions": 0,
                "success_rate": 0.0,
                "average_duration": 0.0,
                "most_used_command": None
            }
        
        total = len(self.execution_history)
        successful = sum(1 for r in self.execution_history if r.success)
        
        # Calculate average duration
        total_duration = sum(r.duration for r in self.execution_history)
        avg_duration = total_duration / total if total > 0 else 0.0
        
        # Find most used command
        command_counts = {}
        for result in self.execution_history:
            target = result.command.target
            command_counts[target] = command_counts.get(target, 0) + 1
        
        most_used = max(command_counts.items(), key=lambda x: x[1])[0] if command_counts else None
        
        return {
            "total_executions": total,
            "success_rate": (successful / total) * 100 if total > 0 else 0.0,
            "average_duration": avg_duration,
            "most_used_command": most_used,
            "currently_running": len(self.active_processes)
        }