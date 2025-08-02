# TUI Project Plan: HIPAA Infrastructure Stack Terminal Interface

## Project Overview

A modern, minimal terminal user interface (TUI) for managing HIPAA-compliant infrastructure using Python and the Textual library. Inspired by the clean aesthetic of [posting](https://github.com/darrenburns/posting), this TUI provides keyboard-driven navigation through Make commands with real-time status monitoring and command output display.

## Design Philosophy

- **Minimal & Modern**: Clean, unobtrusive design with subtle colors and thoughtful spacing
- **Keyboard-First**: All actions accessible via intuitive keyboard shortcuts
- **Context-Aware**: Commands prioritized by frequency and relevance
- **Real-Time**: Live status updates and command output streaming
- **Accessible**: Clear visual hierarchy and keyboard navigation

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  HIPAA Infrastructure Stack TUI                            │
├─────────────────────────────────────────────────────────────┤
│  Status: Repo ✅ | AWS ✅ | Pulumi ✅ | Docker ✅ | 12:34 PM │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌───────────────────────────────────┐ │
│  │   Command Tree  │  │         Output Pane               │ │
│  │                 │  │                                   │ │
│  │ • Development   │  │  $ make deploy-dev                │ │
│  │   ├── Deploy    │  │  🚀 Deploying to development...   │ │
│  │   └── Test      │  │  ✅ VPC created                   │ │
│  │                 │  │  ✅ ECS cluster ready             │ │
│  │ • Production    │  │  🎉 Deployment complete!          │ │
│  │   └── Deploy    │  │                                   │ │
│  │                 │  │                                   │ │
│  └─────────────────┘  └───────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Core Features

### 1. Hierarchical Command Navigation
- **Tree Structure**: Commands organized by environment and category
- **Smart Grouping**: Most common commands prominently displayed
- **Search/Filter**: Type to filter commands in real-time
- **Bookmarks**: Quick access to frequently used commands

### 2. Real-Time Status Bar
- **AWS Connection**: Credential validation and region status
- **Pulumi State**: Stack status and last deployment
- **Local Environment**: Docker, dependencies, and services
- **Cloud Resources**: Active infrastructure summary
- **Auto-refresh**: 30-second updates with manual refresh option

### 3. Command Output Display
- **Streaming Output**: Real-time command execution display
- **Syntax Highlighting**: Color-coded output for better readability
- **Scrollback Buffer**: Navigate through historical output
- **Copy/Paste**: Easy extraction of command results
- **Search Within Output**: Find specific text in command results

### 4. Keyboard Shortcuts

#### Navigation
- `Tab` / `Shift+Tab`: Navigate between panes
- `↑` / `↓`: Navigate command tree
- `→` / `Enter`: Execute selected command
- `←` / `Backspace`: Go back/up one level
- `/`: Search/filter commands
- `Ctrl+r`: Refresh status

#### Command Management
- `Ctrl+e`: Edit command before execution
- `Ctrl+d`: Duplicate command with custom parameters
- `Ctrl+h`: Show command help/description
- `Ctrl+k`: Kill/stop running command
- `Space`: Toggle command bookmark

#### Interface Control
- `Ctrl+l`: Clear output pane
- `Ctrl+f`: Full-screen output mode
- `Ctrl+t`: Toggle theme (dark/light)
- `q` / `Ctrl+c`: Quit application

## Technical Requirements

### Dependencies
```python
textual>=0.45.0          # Modern TUI framework
rich>=13.0.0            # Rich text and formatting
pyyaml>=6.0             # YAML configuration
click>=8.0.0            # Command-line interface
watchdog>=3.0.0         # File system monitoring
psutil>=5.9.0           # System monitoring
boto3>=1.26.0           # AWS SDK
pulumi>=3.0.0           # Infrastructure as Code
```

### System Requirements
- Python 3.8+
- Terminal with 256-color support
- Minimum 80x24 terminal size
- Recommended: 120x40 or larger

## Command Categories

### 1. Development Environment
```
├── 🔧 Setup & Install
│   ├── install              # Install all dependencies
│   ├── setup-env-dev        # Setup development environment
│   └── verify               # Verify installations
├── 🚀 Application
│   ├── dev-app              # Start development containers
│   ├── dev-logs             # View application logs
│   └── dev-stop             # Stop development environment
└── 🧪 Testing
    ├── test                 # Run comprehensive tests
    ├── test-app             # Test application only
    └── lint                 # Code quality checks
```

### 2. Infrastructure Management
```
├── 👁️ Preview
│   ├── preview-dev          # Preview dev changes
│   ├── preview-staging      # Preview staging changes
│   └── preview-prod         # Preview production changes
├── 🏗️ Deploy
│   ├── deploy-dev           # Deploy development infrastructure
│   ├── deploy-staging       # Deploy staging infrastructure
│   └── deploy-prod          # Deploy production infrastructure
└── 🧹 Cleanup
    ├── clean-dev            # Destroy dev infrastructure
    ├── clean-staging        # Destroy staging infrastructure
    └── clean-prod           # Destroy production infrastructure
```

### 3. Monitoring & Diagnostics
```
├── 📊 Status
│   ├── status               # Pulumi stack status
│   ├── show-outputs         # Display deployment outputs
│   └── list-aws-resources   # Show AWS resources
├── 📈 Diagrams
│   ├── generate-diagrams    # Create infrastructure diagrams
│   ├── generate-network     # Network architecture
│   └── generate-security    # Security architecture
└── 🔍 Validation
    ├── validate-env-dev     # Validate dev environment
    └── validate-config      # Check configuration
```

### 4. Emergency & Maintenance
```
├── 🚨 Emergency
│   ├── emergency-clean-dev  # Emergency dev cleanup
│   └── rotate-keys-info     # AWS key rotation guide
└── 🔧 Utilities
    ├── create-config        # Create example configuration
    └── edit-config          # Edit environments.yaml
```

## UI Components

### 1. Command Tree Panel
- **Location**: Left sidebar (25% width)
- **Features**:
  - Expandable/collapsible categories
  - Visual indicators for command types
  - Progress indicators for running commands
  - Color-coded by environment (dev=blue, staging=yellow, prod=red)

### 2. Output Pane
- **Location**: Main area (75% width)
- **Features**:
  - Scrollable terminal output
  - Syntax highlighting for logs
  - Progress bars for long-running tasks
  - Error highlighting with expandable details

### 3. Status Bar
- **Location**: Top of screen (persistent)
- **Features**:
  - **Repo Status**: Setup verification (dependencies, config files)
  - **AWS Connection**: Credential validation and region status
  - **Pulumi State**: Stack status and last deployment
  - **Docker/Container**: Engine status and container health
  - **Current Time**: Last refresh timestamp
  - **Refresh Indicator**: Shows when status is being updated

### 4. Modal Dialogs
- **Command Preview**: Show full command before execution
- **Parameter Input**: Custom parameters for commands
- **Help System**: Contextual help for commands
- **Confirmation**: Critical action confirmation

## Status Monitoring

### AWS Resources
- **Credential Validation**: Check AWS CLI and profiles
- **Regional Status**: Verify region accessibility
- **Service Health**: ECS, RDS, ALB status
- **Resource Counts**: Active VPCs, instances, databases

### Local Environment
- **Docker**: Engine status and container health
- **Dependencies**: Poetry, Pulumi, AWS CLI availability
- **Configuration**: Environment files and settings
- **Network**: Internet connectivity and AWS endpoint access

### Pulumi State
- **Stack Status**: Current stack state (dev/staging/prod)
- **Last Deployment**: Timestamp and success/failure
- **Pending Changes**: Resources to be created/modified/destroyed
- **Configuration**: Backend and encryption status

## Configuration

### YAML Structure
```yaml
tui:
  refresh_interval: 30
  max_output_lines: 10000
  themes:
    default: dark
    options: [dark, light, high_contrast]
  
commands:
  favorites:
    - "deploy-dev"
    - "dev-app"
    - "test"
  
  categories:
    development:
      priority: high
      commands: [...]
    infrastructure:
      priority: high
      commands: [...]
    monitoring:
      priority: medium
      commands: [...]

environments:
  dev:
    color: "#4299e1"
    aws_profile: "pulumi-deploy-user-dev"
  staging:
    color: "#ed8936"
    aws_profile: "pulumi-deploy-user-staging"
  prod:
    color: "#e53e3e"
    aws_profile: "pulumi-deploy-user-prod"
```

### Environment Detection
- **Automatic**: Detect current directory and environment
- **Manual Override**: Allow user to switch environments
- **Profile Validation**: Verify AWS profiles exist
- **Smart Defaults**: Suggest based on current context

## Implementation Phases

### 📋 Development Workflow Guidelines

**CRITICAL REQUIREMENTS FOR ALL PHASES:**

1. **Use Sub-Agents Proactively**: Leverage Task tool with specialized agents for complex tasks
2. **Test Before Commit**: Run comprehensive tests after each phase completion
3. **Commit After Success**: Create git commits only after tests pass
4. **Update Progress**: Keep this TUI_PLAN.md updated with completed phases
5. **Track with TodoWrite**: Use todo management for each phase's subtasks

#### Git Commit Workflow
```bash
# After each phase completion:
git add .
git commit -m "Complete Phase X: [Phase Description]

## Summary
- [Key accomplishments]
- [Tests passing]
- [Components implemented]

## Technical Details
- [Specific technical achievements]
- [Infrastructure resources deployed]
- [Application features implemented]

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

#### Sub-Agent Usage Examples
```bash
# Use Task tool for complex tasks:
Task(description="Implement TUI core framework", 
     prompt="Create complete Textual TUI framework including app.py, basic layout with status bar, command tree, and output pane. Include keyboard navigation and Makefile parsing. Follow the exact file structure specified in TUI_PLAN.md.",
     subagent_type="general-purpose")

Task(description="Test phase 1 components", 
     prompt="Create comprehensive tests for TUI phase 1 including unit tests for command parsing, keyboard handling, and layout components. Ensure all tests pass before proceeding.",
     subagent_type="general-purpose")
```

### 🎯 Phase Tracking Dashboard

**Current Status**: Planning Phase

| Phase | Status | Progress | Tests | Commit |
|-------|--------|----------|-------|--------|
| **Phase 1** | 🔄 Pending | 0/4 tasks | ❌ | ❌ |
| **Phase 2** | ⏸️ Not Started | 0/4 tasks | ❌ | ❌ |
| **Phase 3** | ⏸️ Not Started | 0/5 tasks | ❌ | ❌ |
| **Phase 4** | ⏸️ Not Started | 0/4 tasks | ❌ | ❌ |

### Phase 1: Core Framework
**Status**: 🔄 **Ready to Start**

**Tasks**:
- [ ] Textual application setup (`tui/app.py`)
- [ ] Basic layout with three panels (status bar, command tree, output)
- [ ] Keyboard navigation system (Tab, arrows, shortcuts)
- [ ] Command tree parsing from Makefile

**Testing Requirements**:
- [ ] Unit tests for keyboard navigation
- [ ] Command tree parsing accuracy tests
- [ ] Layout rendering tests
- [ ] Keyboard shortcut handling tests

**Sub-Agent Recommendations**:
- Use Task tool for Textual app setup
- Use Task tool for Makefile parsing
- Use Task tool for keyboard system implementation

### Phase 2: Command Execution
**Status**: ⏸️ **Waiting for Phase 1**

**Tasks**:
- [ ] Makefile command discovery and parsing
- [ ] Command execution with streaming output
- [ ] Error handling and retry mechanisms
- [ ] Progress indicators and status updates

**Testing Requirements**:
- [ ] Command execution tests
- [ ] Output streaming tests
- [ ] Error handling tests
- [ ] Progress indicator tests

### Phase 3: Status Monitoring
**Status**: ⏸️ **Waiting for Phase 2**

**Tasks**:
- [ ] Repository setup verification (dependencies, config, git hooks)
- [ ] AWS credential validation
- [ ] Pulumi stack status integration
- [ ] Docker/container health checks
- [ ] Real-time status bar updates

**Testing Requirements**:
- [ ] AWS connectivity tests
- [ ] Pulumi integration tests
- [ ] Docker health check tests
- [ ] Status bar update tests
- [ ] Repository validation tests

### Phase 4: Polish & Optimization
**Status**: ⏸️ **Waiting for Phase 4**

**Tasks**:
- [ ] Performance optimization
- [ ] Accessibility improvements
- [ ] Comprehensive testing
- [ ] Documentation and examples

**Testing Requirements**:
- [ ] Performance benchmark tests
- [ ] Accessibility compliance tests
- [ ] End-to-end workflow tests
- [ ] Documentation validation tests

### 📊 Progress Update Template

After completing each phase, update this section:

```markdown
## Phase X: [Phase Name] - ✅ COMPLETED

**Completion Date**: [Date]
**Tests**: ✅ All tests passing
**Commit**: [Commit hash]

### What Was Implemented
- [List specific accomplishments]
- [Key features completed]
- [Bug fixes resolved]

### Testing Results
- [Test suite results]
- [Performance benchmarks]
- [User acceptance criteria met]

### Next Steps
- [Link to next phase planning]
- [Blockers identified]
- [Dependencies for next phase]
```

## Implementation Checklist

### Pre-Implementation Setup
- [ ] Ensure TodoWrite is available for task tracking
- [ ] Verify git repository is initialized and clean
- [ ] Confirm Python 3.8+ and Poetry are installed
- [ ] Run `make verify` to check all dependencies

### Phase Execution Checklist
For each phase:
1. ✅ **Create Phase Tasks** using TodoWrite
2. ✅ **Use Sub-Agents** for complex multi-file tasks
3. ✅ **Run Tests** for the specific phase
4. ✅ **Update TUI_PLAN.md** with progress
5. ✅ **Create Git Commit** only after tests pass
6. ✅ **Verify Next Phase** dependencies are ready

### Emergency Procedures
- **Test Failure**: Investigate immediately, fix before proceeding
- **Git Issues**: Use `git status` to verify clean working directory
- **Dependency Issues**: Run `make install` to refresh dependencies
- **Permission Issues**: Verify AWS profiles and credentials

## File Structure

```
tui/
├── app.py                 # Main TUI application
├── components/
│   ├── __init__.py
│   ├── command_tree.py   # Command tree widget
│   ├── output_pane.py    # Output display widget
│   ├── status_bar.py     # Status bar widget
│   └── modals.py         # Dialog boxes
├── models/
│   ├── __init__.py
│   ├── command.py        # Command data structures
│   └── status.py         # Status monitoring
├── services/
│   ├── __init__.py
│   ├── makefile_parser.py # Makefile parsing
│   ├── aws_checker.py    # AWS status validation
│   └── executor.py       # Command execution
├── themes/
│   ├── __init__.py
│   ├── dark.py          # Dark theme colors
│   └── light.py         # Light theme colors
├── config/
│   ├── default.yaml     # Default configuration
│   └── keybindings.yaml # Keyboard shortcuts
└── tests/
    ├── __init__.py
    ├── test_commands.py
    └── test_status.py
```

## Usage Examples

### Starting the TUI
```bash
# From project root
make tui

# Or directly
python tui/app.py

# With specific environment
python tui/app.py --env dev
```

## Testing Strategy

### Unit Tests
- Command parsing accuracy
- Status monitoring correctness
- Keyboard handling
- Theme switching

### Integration Tests
- Makefile command execution
- AWS connectivity validation
- Pulumi integration
- Error handling scenarios

### End-to-End Tests
- Complete user workflows
- Keyboard navigation
- Real-world usage scenarios
- Performance under load

## Security Considerations

### Credential Management
- **No Storage**: Never store AWS credentials
- **Environment Variables**: Use existing AWS profiles
- **Secure Execution**: Commands run in secure subprocesses
- **Audit Trail**: Log command execution (without sensitive data)

### Access Control
- **Profile Validation**: Verify AWS profiles exist
- **Permission Checks**: Validate required permissions
- **Safe Commands**: Prevent dangerous operations without confirmation
- **Read-Only Mode**: Option for viewing without execution
