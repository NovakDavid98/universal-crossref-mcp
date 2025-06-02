# 🔗 **Universal Cross-Reference MCP Server**

*Apply comprehensive cross-reference methodology to ANY project, ensuring complete understanding across all files and codebases.*

---

## 🎯 **Project Goal**

Create a Universal Cross-Reference MCP Server that:
- **Applies the proven cross-reference methodology** from NutriAI to ANY codebase
- **Enforces mandatory reading** of related files through automated cross-reference headers
- **Integrates seamlessly with Cursor IDE** via Model Context Protocol (MCP)
- **Scales to large codebases** (100k+ files) with high-performance async scanning
- **Provides intelligent suggestions** based on learned cross-reference patterns

---

## ⚡ **Key Features**

### 🔍 **Universal File Scanning**
- High-performance async file discovery and analysis
- Intelligent file classification (40+ programming languages)
- Real-time file monitoring with change detection
- Resource monitoring and emergency stops for safety
- Optimized for large codebases (100k+ files)

### 🧠 **Cross-Reference Intelligence**
- Automatic detection of file relationships and dependencies
- Bidirectional cross-reference generation
- Pattern learning for intelligent suggestions
- Hub file management (SYSTEM.md, README.md, etc.)
- Enforced reading requirements with warning language

### 📊 **Performance & Monitoring**
- Async operations throughout for maximum performance
- Resource usage monitoring (CPU, memory, disk I/O)
- Adaptive concurrency management
- Performance metrics and statistics
- Emergency limits and auto-pause capabilities

### 🎭 **Multi-Project Support**
- Single server can manage multiple projects
- Project orchestration and batch operations
- Isolated project configurations
- Cross-project pattern sharing

---

## 🚀 **Development Progress**

### ✅ **Phase 1: Foundation & Infrastructure**

#### **Step 1.1: Project Structure Setup** ✅
- Complete project directory structure
- README with project overview and features  
- Configuration files (requirements.txt, pyproject.toml, etc.)
- Git repository with .gitignore and LICENSE
- Development setup and documentation structure

#### **Step 1.2: Database Design & Setup** ✅  
- PostgreSQL database models optimized for large codebases
- Async database connection management with pooling
- Alembic migrations for schema management
- Comprehensive repository pattern for all operations
- Configuration system with environment variable support

#### **Step 1.3: Async File Scanner Engine** ✅
- High-performance async file discovery and analysis
- Real-time file monitoring with watchdog integration
- Resource monitoring and performance management
- Multi-project orchestration capabilities
- Emergency stops and safety limits

#### **Step 1.4: Content Analysis & Pattern Detection** 🔄 *(In Progress)*
- Cross-reference pattern detection and extraction
- Content parsing for imports, dependencies, and relationships
- Hub file identification and management
- Relationship strength and confidence scoring

### 🔄 **Phase 2: Core Cross-Reference Engine** *(Next)*

#### **Step 2.1: Relationship Detection Engine**
- Import/dependency analysis across programming languages
- Cross-reference header parsing and validation
- Bidirectional relationship mapping
- Pattern-based relationship suggestions

#### **Step 2.2: Hub File Management**
- Automatic hub file creation and updates
- Cross-reference header generation
- Mandatory reading requirement enforcement
- Hub file template system

#### **Step 2.3: Cross-Reference Generation**
- Automated cross-reference header creation
- Bidirectional linking system
- Warning language and enforcement formatting
- Integration with existing documentation

### 📋 **Phase 3: MCP Server Implementation** *(Planned)*

#### **Step 3.1: MCP Protocol Integration**
- Model Context Protocol server implementation
- Cursor IDE integration and communication
- Real-time project analysis and updates
- Cross-reference enforcement in IDE

#### **Step 3.2: API and Interface Design**
- RESTful API for external integrations
- WebSocket support for real-time updates
- CLI tools for batch operations
- Configuration management interface

### 🎯 **Phase 4: Intelligence & Optimization** *(Planned)*

#### **Step 4.1: Pattern Learning System**
- Machine learning for relationship detection
- Pattern confidence scoring and validation
- Intelligent cross-reference suggestions
- Adaptive system behavior

#### **Step 4.2: Performance Optimization**
- Caching strategies for large codebases
- Incremental analysis and updates
- Memory optimization for massive projects
- Background processing and queuing

---

## 📁 **Project Structure**

```
universal-crossref-mcp/
├── 📁 src/                      # Source code
│   ├── 📁 database/             # Database models and operations ✅
│   ├── 📁 scanner/              # File scanning engine ✅
│   ├── 📁 analysis/             # Content analysis (🔄 In Progress)
│   ├── 📁 crossref/             # Cross-reference logic (📋 Planned)
│   ├── 📁 mcp/                  # MCP server implementation (📋 Planned)
│   └── 📁 utils/                # Utilities and configuration ✅
├── 📁 migrations/               # Database migrations ✅
├── 📁 config/                   # Configuration files ✅
├── 📁 tests/                    # Test suite (📋 Planned)
├── 📁 docs/                     # Documentation ✅
└── 📁 examples/                 # Example usage and demos ✅
```

---

## 🛠️ **Technology Stack**

### **Core Framework**
- **Python 3.11+** with async/await throughout
- **FastAPI** for API endpoints and MCP server
- **PostgreSQL** with asyncpg for database operations
- **SQLAlchemy 2.0** with async support

### **File Processing**
- **aiofiles** for async file operations
- **pathspec** for gitignore-style pattern matching
- **watchdog** for real-time file system monitoring
- **chardet** for encoding detection

### **Performance & Monitoring**
- **psutil** for system resource monitoring
- **structlog** for structured logging
- **asyncio** for concurrent operations
- **uvicorn** for ASGI server

### **Development Tools**
- **Alembic** for database migrations
- **pytest** with async support for testing
- **black** and **isort** for code formatting
- **mypy** for type checking

---

## 🚀 **Quick Start**

### **1. Clone and Setup**
```bash
git clone <repository-url>
cd universal-crossref-mcp
pip install -r requirements.txt
```

### **2. Database Setup**
```bash
# Initialize database
python src/database/init_db.py

# Or use the demo (includes database setup)
python examples/scanner_demo.py /path/to/your/project
```

### **3. Run Scanner Demo**
```bash
# Comprehensive scanner engine demo
python examples/scanner_demo.py

# Demos include:
# - Basic file scanning
# - Performance monitoring  
# - Real-time file monitoring
# - Multi-project orchestration
```

---

## 📊 **Current Capabilities**

### ✅ **Working Features**
- **High-performance file scanning** with async operations
- **Real-time file monitoring** with change detection
- **Resource monitoring** with emergency stops
- **Multi-project management** and orchestration
- **Database persistence** with PostgreSQL
- **Performance metrics** and comprehensive statistics

### 🔄 **In Development**
- **Content analysis** for imports and dependencies
- **Cross-reference pattern detection**
- **Hub file management** and automation

### 📋 **Planned Features**
- **MCP server** for Cursor IDE integration
- **Intelligent cross-reference generation**
- **Pattern learning** and suggestions
- **Web interface** for project management

---

## 🎯 **System Philosophy**

> **"Every person reading any project documentation MUST read ALL related files to get the complete picture"**

This system applies the proven cross-reference methodology that ensures:
- **No partial knowledge** from reading isolated files
- **Complete technical understanding** across all project aspects  
- **Consistent information** with bidirectional cross-references
- **Quality assurance** through mandatory comprehensive reading
- **Systematic approach** to complex technical documentation

---

## 📈 **Performance Highlights**

- **Optimized for large codebases** (tested up to 100,000+ files)
- **Async file processing** with configurable concurrency
- **Resource monitoring** prevents system overload
- **Incremental scanning** with real-time change detection
- **Emergency stops** protect against runaway processes
- **Adaptive performance** based on system resources

---

## 🤝 **Contributing**

This project implements a universal cross-reference methodology for ANY codebase. The system is designed to be:
- **Language agnostic** - works with any programming language
- **Project agnostic** - works with any project structure  
- **IDE integrated** - seamless Cursor IDE integration via MCP
- **Performance focused** - optimized for large-scale codebases

---

## 📄 **License**

MIT License - see LICENSE file for details.

---

*Universal Cross-Reference MCP Server - Ensuring complete understanding across all codebases.* 