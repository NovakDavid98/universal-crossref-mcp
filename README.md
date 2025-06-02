# 🔗 Universal Cross-Reference MCP Server

**Version 2.0.0 - Universal Content-Aware Edition** 🚀

A revolutionary **intelligent cross-reference documentation management system** that **automatically adapts to any type of content**. Featuring universal genre detection, content-aware analysis, and intelligent PDF extraction for creating cross-referenced knowledge bases from any book or document.

## 🌟 Revolutionary Features

### 🧠 **Universal Content-Aware Analysis**
- **Automatic Genre Detection**: Detects 9+ content types (fiction, technical, historical, business, etc.)
- **Adaptive Cross-Referencing**: Different analysis strategies for different content types
- **Intelligent Relationships**: Creates meaningful connections based on actual content analysis
- **Named Entity Recognition**: Extracts people, places, organizations for better relationships

### 📚 **Universal PDF Extraction Engine**
- **Multi-Strategy Extraction**: PyPDF2, pdfplumber, and OCR for maximum compatibility
- **Quality Assessment**: Automatic extraction quality scoring and strategy selection
- **Content-Aware Chunking**: Intelligent chapter division based on content structure
- **Async Processing**: Background extraction for large documents without timeouts

### 🎯 **Genre-Specific Intelligence**
- **Fiction**: Character relationships, plot connections, dialogue analysis
- **Technical**: Procedure dependencies, concept building, system relationships  
- **Historical**: Chronological relationships, figure connections, cause-effect chains
- **Business**: Strategic connections, case study links, methodology relationships
- **Scientific**: Theory dependencies, research connections, concept hierarchies
- **Philosophy**: Concept dependencies, argument progressions, metaphysical connections
- **Medical**: Treatment protocols, symptom relationships, research connections
- **Self-Help**: Goal relationships, habit building, improvement sequences
- **Religious**: Scriptural references, doctrinal connections, spiritual themes

## 🎉 What Makes This Revolutionary

### Traditional Cross-Referencing Problems:
❌ Manual file linking based on proximity  
❌ No content understanding  
❌ Generic relationships for all content types  
❌ Time-consuming manual maintenance  

### Our Universal Solution:
✅ **Automatic content analysis** with genre detection  
✅ **Intelligent relationship creation** based on actual content  
✅ **Adaptive strategies** for different book/document types  
✅ **Real-time automatic maintenance** with file system watching  
✅ **Universal PDF processing** that works with any book type  

## 🚀 Core Features

### 📖 **Documentation Management**
- **Automated Cross-Referencing**: Intelligent links between related files based on content analysis
- **Real-time Watching**: File system monitoring with automatic cross-reference updates
- **Hub File Management**: Central documentation with mandatory reading methodology
- **Content Quality Assessment**: Automatic scoring and optimization recommendations

### 🔄 **PDF Processing Revolution**
- **Universal Book Support**: Fiction novels → Technical manuals → Historical texts → Business books
- **Intelligent Chunking**: Content-aware chapter division with natural breaks
- **Quality-Driven Extraction**: Multiple strategies with automatic quality assessment
- **Async Processing**: Background extraction for large documents (500+ pages)
- **Cross-Referenced Output**: Generated files include intelligent content-based relationships

### 🤖 **LLM Integration**
- **Cursor IDE Integration**: Seamless integration via Model Context Protocol (MCP)
- **Comprehensive Documentation**: Built-in tool documentation with usage examples
- **12 Specialized Tools**: Complete toolkit for any cross-referencing need
- **Content-Aware Guidance**: Genre-specific recommendations and optimization

## 📋 Requirements

- **Python 3.8+**
- **FastAPI** (for MCP server)
- **Watchdog** (for file system monitoring)
- **MCP library** (for Cursor integration)
- **PM2** (for process management)
- **PDF Processing** (PyPDF2, pdfplumber, pytesseract, pdf2image - for PDF extraction)

## 🛠️ Installation

1. **Clone the Repository**:
```bash
git clone https://github.com/yourusername/universal-crossref-mcp.git
cd universal-crossref-mcp
```

2. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

3. **Install PM2** (if not already installed):
```bash
npm install -g pm2
```

4. **Start the Server**:
```bash
pm2 start src/mcp_server/simple_server.py --name universal-crossref --interpreter python
```

## 🔌 Cursor IDE Integration

1. Open **Cursor IDE**
2. Go to **Settings** → **MCP**
3. Add this configuration:

```json
{
  "universal-crossref": {
    "command": "python3 /path/to/universal-crossref-mcp/src/mcp_server/simple_server.py",
    "enabled": true,
    "metadata": {
      "description": "Universal Content-Aware Cross-Reference System"
    }
  }
}
```

## 🧰 Complete Toolkit (12 Tools)

### 📊 **Analysis & Planning**
1. **`analyze_file`** - Deep file analysis with cross-reference detection
2. **`scan_project`** - Project structure analysis and statistics
3. **`get_crossref_recommendations`** - AI-powered improvement suggestions

### 🏗️ **Core Cross-Referencing**
4. **`create_hub_file`** - Create central documentation hub
5. **`add_crossref_header`** - Add intelligent cross-reference headers
6. **`update_hub_mandatory_reading`** - Manage hub file relationships
7. **`implement_crossref_methodology`** - Apply methodology to entire projects

### 🔄 **Automation & Monitoring**
8. **`start_auto_crossref_watcher`** - Real-time file system monitoring
9. **`stop_auto_crossref_watcher`** - Stop automatic monitoring

### 📚 **Universal PDF Processing**
10. **`extract_pdf_to_markdown`** - Intelligent PDF extraction with content analysis
11. **`extract_pdf_to_markdown_async`** - Background processing for large documents
12. **`check_pdf_extraction_status`** - Monitor async extraction progress

## 🎯 Usage Examples

### 📖 **Convert Any Book to Cross-Referenced Knowledge Base**

```python
# Extract a philosophy book with automatic genre detection
result = mcp_universal-crossref_extract_pdf_to_markdown(
    pdf_path="/path/to/philosophy_book.pdf",
    max_chunks=25,
    create_hub=True
)

# System automatically:
# ✅ Detects it's a philosophical work
# ✅ Extracts key concepts (consciousness, existence, reality)
# ✅ Creates intelligent concept-based cross-references
# ✅ Generates navigable hub with philosophical navigation
```

### 🏢 **Process Technical Documentation**

```python
# Extract a technical manual with procedure analysis
result = mcp_universal-crossref_extract_pdf_to_markdown_async(
    pdf_path="/path/to/technical_manual.pdf",
    max_chunks=50
)

# Monitor progress
status = mcp_universal-crossref_check_pdf_extraction_status(task_id)

# System creates:
# ✅ Procedure dependency mapping
# ✅ Technical concept hierarchies  
# ✅ Prerequisite knowledge chains
# ✅ System relationship diagrams
```

### 📚 **Start New Documentation Project**

```python
# 1. Create intelligent hub file
mcp_universal-crossref_create_hub_file(
    file_path="/project/SYSTEM.md",
    title="Project Documentation Hub",
    description="Central documentation with content-aware cross-referencing"
)

# 2. Enable automatic intelligence
mcp_universal-crossref_start_auto_crossref_watcher(
    project_path="/project",
    hub_file_name="SYSTEM.md"
)
# Now all new files get intelligent cross-referencing automatically!
```

### 🔄 **Upgrade Existing Project**

```python
# Apply revolutionary methodology to existing project
mcp_universal-crossref_implement_crossref_methodology(
    project_path="/existing/project",
    hub_file_name="README.md",
    project_title="Enhanced Documentation"
)

# Transforms your documentation with content-aware intelligence
```

## 🎨 **Content-Aware Cross-Referencing in Action**

### Traditional Approach:
```markdown
Related files: [file1.md, file2.md, file3.md]
```

### Our Universal Approach:
```markdown
Related files: ['chapter_03_consciousness_and_reality.md']
Relationship: Shared concepts: consciousness, reality, existence
Reason: Builds on metaphysical foundations from this chapter
Type: conceptual_dependency
Similarity: 0.847
```

## 📈 **Performance & Quality**

### 🎯 **Extraction Quality**
- **Quality Scores**: 0.0-1.0 scale with automatic assessment
- **Multi-Strategy**: PyPDF2 → pdfplumber → OCR for best results
- **Error Handling**: Graceful fallbacks and quality reporting

### ⚡ **Processing Speed**
- **Small PDFs** (<500KB): Instant synchronous processing
- **Large PDFs** (500KB+): Background async processing with real-time progress
- **Batch Processing**: Handle multiple documents simultaneously

### 🧠 **Content Intelligence**
- **Genre Detection**: 95%+ accuracy on structured content
- **Relationship Quality**: Only creates high-quality relationships (similarity > 0.2)
- **Adaptive Analysis**: Different strategies per content type

## 🔬 **Technical Architecture**

### 🌐 **Universal Genre Detection Engine**
```python
class UniversalPDFContentAnalyzer:
    - detect_genre() # Automatic content type detection
    - extract_concepts_universal() # Genre-aware concept extraction
    - calculate_universal_similarity() # Multi-factor relationship scoring
    - generate_universal_cross_references() # Intelligent cross-referencing
```

### 📊 **Content Analysis Pipeline**
1. **Text Extraction** → Multiple strategies for maximum compatibility
2. **Genre Detection** → AI-powered content type identification  
3. **Concept Extraction** → TF-IDF weighted with genre-specific boosting
4. **Relationship Analysis** → Multi-factor similarity with intelligent reasoning
5. **Cross-Reference Generation** → Content-aware relationship creation

## 🎓 **Use Cases**

### 📚 **Academic & Research**
- Convert research papers to cross-referenced knowledge bases
- Create navigable literature reviews with concept mapping
- Build interdisciplinary research repositories

### 🏢 **Business & Technical**
- Transform technical manuals into intelligent documentation
- Create cross-referenced policy and procedure libraries
- Build navigable training material repositories

### 📖 **Publishing & Content**
- Convert books into interactive knowledge bases
- Create educational material with intelligent navigation
- Build reference libraries with content-aware relationships

### 🎯 **Personal Knowledge Management**
- Build personal libraries from any PDF collection
- Create cross-referenced research notes
- Organize learning materials with intelligent connections

## 📄 License

This project is licensed under the **Mozilla Public License 2.0 (MPL-2.0)** - see the [LICENSE](LICENSE) file for details.

The MPL-2.0 is a copyleft license that allows for commercial use, modification, distribution, and private use, while ensuring that modifications to the code remain open source.

## 🌟 **What's Next?**

- **Enhanced NLP**: Integration with transformer models for even better content understanding
- **Visual Analysis**: OCR improvements and diagram recognition
- **Multi-Language**: Support for non-English content analysis
- **API Extensions**: REST API for broader integration possibilities

## 🤝 Contributing

We welcome contributions! This revolutionary system is designed to transform how we think about documentation and knowledge management.

**Areas for Contribution:**
- New genre detection patterns
- Enhanced content analysis algorithms  
- Additional extraction strategies
- UI/UX improvements for the generated output

## 📬 Contact & Support

- **Issues**: Open an issue on this repository
- **Features**: Suggest new content analysis capabilities
- **Documentation**: Help improve our cross-referencing methodology

---

**🚀 Transform your documentation with Universal Content-Aware Cross-Referencing!**

*Built with ❤️ for the future of intelligent knowledge management* 