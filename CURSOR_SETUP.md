# 🔗 Universal Cross-Reference MCP Server - Cursor Setup

## 🎯 Quick Setup Guide

### 1. **Copy MCP Configuration**

Copy this configuration to your Cursor MCP settings:

```json
{
  "mcpServers": {
    "universal-crossref": {
      "command": "python",
      "args": [
        "/home/frontalneuralcortex/crossrefference/universal-crossref-mcp/run_server.py"
      ],
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://crossref_user:crossref123@localhost:5432/crossref_db",
        "PYTHONPATH": "/home/frontalneuralcortex/crossrefference/universal-crossref-mcp"
      }
    }
  }
}
```

### 2. **Access in Cursor**

Once configured, you'll have access to these powerful tools in Cursor:

#### 🔍 **analyze_file**
Analyze any file for cross-reference patterns:
```
file_path: "path/to/your/file.py" 
```

#### 🔗 **analyze_project** 
Comprehensive project analysis:
```
project_path: "/path/to/your/project"
project_name: "MyProject" (optional)
```

#### 💡 **get_crossref_recommendations**
Get intelligent suggestions:
```
project_path: "/path/to/your/project"
```

#### 🏛️ **detect_hub_files**
Find central documentation:
```
project_path: "/path/to/your/project"
```

#### 📊 **analyze_relationships**
Dependency analysis:
```
project_path: "/path/to/your/project"
```

## 🚀 **Test with This Project**

Try analyzing this very project:

```bash
# Test the Universal Cross-Reference system on itself
analyze_project:
  project_path: "/home/frontalneuralcortex/crossrefference/universal-crossref-mcp"
```

## 📋 **What You'll Get**

- **Import/Export Analysis**: Complete dependency mapping
- **Hub File Detection**: Identify central documentation 
- **Pattern Recognition**: Cross-reference headers, documentation patterns
- **Quality Scoring**: Measure documentation completeness
- **Smart Recommendations**: Actionable improvement suggestions
- **Relationship Graphs**: Visual dependency analysis

## 🔧 **Advanced Features**

### Multi-Language Support
- Python (AST parsing)
- JavaScript/TypeScript (ES6/CommonJS)
- Markdown (links and headers)
- Text files (patterns and references)

### Cross-Reference Methodology
Implements the proven cross-reference approach:
- Mandatory reading patterns
- Hub file networks  
- Quality assessments
- Bidirectional references

## 🎯 **Use Cases in Cursor**

1. **Before Refactoring**: Understand impact with `analyze_relationships`
2. **Documentation Audit**: Check coverage with `get_crossref_recommendations`  
3. **New Team Member**: Map learning path with `detect_hub_files`
4. **Code Review**: Ensure proper cross-references with `analyze_file`
5. **Project Health**: Overall assessment with `analyze_project`

---

**Ready to revolutionize your codebase understanding! 🚀** 