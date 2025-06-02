## 🧰 The 10 Tools

### 🔍 **Analysis Tools** (Read-Only)
1. **`analyze_file`** - Analyze single file
2. **`scan_project`** - Project overview  
3. **`get_crossref_recommendations`** - Smart suggestions

### ✏️ **Implementation Tools** (Write Operations)
4. **`create_hub_file`** - Create central hub
5. **`add_crossref_header`** - Add headers to files
6. **`update_hub_mandatory_reading`** - Update hub lists
7. **`implement_crossref_methodology`** - Apply to entire project

### 📚 **PDF Processing Tools** (NEW!)
8. **`extract_pdf_to_markdown`** - Convert PDF to cross-referenced markdown files

### 🤖 **Automation Tools**
9. **`start_auto_crossref_watcher`** - Auto file monitoring
10. **`stop_auto_crossref_watcher`** - Stop monitoring 

### **Example 3: Manual Fine-Tuning**

**Add Header to Specific File:**
```
Tool: add_crossref_header
Parameters:
- file_path: "/project/new-feature.md"
- hub_file: "SYSTEM.md"
- related_files: ["api.md", "config.md"]
```

**Update Hub File:**
```
Tool: update_hub_mandatory_reading
Parameters:
- hub_file_path: "/project/SYSTEM.md"
- new_files: ["new-feature.md", "troubleshooting.md"]
- files_to_remove: ["deprecated-guide.md"]
```

### **Example 4: PDF to Markdown Conversion (NEW!)**

**Step 1: Extract PDF to Cross-Referenced Markdown**
```
Tool: extract_pdf_to_markdown
Parameters:
- pdf_path: "/project/Machine_Learning_Textbook.pdf"
- max_chunks: 25
- create_hub: true
```

**This Creates:**
```
/project/
├── Machine_Learning_Textbook_extracted/
│   ├── machine_learning_textbook_hub.md
│   ├── machine_learning_textbook_01_introduction.md
│   ├── machine_learning_textbook_02_supervised_learning.md
│   ├── machine_learning_textbook_03_neural_networks.md
│   └── ... (22 more chapters)
```

**Each extracted file gets:**
```markdown
# Machine Learning Textbook 01 Introduction

**⚠️ IMPORTANT**: When reading this file you HAVE TO read: [machine_learning_textbook_hub.md](machine_learning_textbook_hub.md)

**Cross-reference**: This document supplements machine_learning_textbook_hub.md. Also read: [machine_learning_textbook_02_supervised_learning.md](machine_learning_textbook_02_supervised_learning.md)

**Extracted from PDF**: Machine_Learning_Textbook.pdf
**Chunk**: 1 of 25

---

# Your extracted PDF content here...
```

**Step 2: Start Auto-Watching (Optional)**
```
Tool: start_auto_crossref_watcher
Parameters:
- project_path: "/project/Machine_Learning_Textbook_extracted"
- hub_file_name: "machine_learning_textbook_hub.md"
```

## 🎯 Quick Reference

| **Goal** | **Tool** | **When to Use** |
|----------|----------|-----------------|
| Understand project | `scan_project` | First step, get overview |
| Analyze specific file | `analyze_file` | Deep dive into imports/patterns |
| Get improvement ideas | `get_crossref_recommendations` | Periodic checkups |
| Create central hub | `create_hub_file` | New projects |
| Add header to file | `add_crossref_header` | Manual header management |
| Update hub lists | `update_hub_mandatory_reading` | Hub maintenance |
| Apply to all files | `implement_crossref_methodology` | Existing project retrofit |
| **Convert PDF to markdown** | **`extract_pdf_to_markdown`** | **Extract knowledge from PDFs** |
| Auto-manage changes | `start_auto_crossref_watcher` | Ongoing maintenance |
| Stop auto-updates | `stop_auto_crossref_watcher` | Before bulk edits | 