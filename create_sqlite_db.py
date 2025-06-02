#!/usr/bin/env python3
"""Simple SQLite database creation for Universal Cross-Reference MCP Server"""

import sqlite3
import os
from pathlib import Path

def create_sqlite_database():
    """Create SQLite database with basic tables for the MCP server."""
    
    # Database path
    db_path = Path(__file__).parent / "crossref.db"
    
    # Remove existing database
    if db_path.exists():
        os.remove(db_path)
    
    # Create connection
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create projects table
        cursor.execute("""
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                root_path TEXT NOT NULL,
                hub_file TEXT DEFAULT 'SYSTEM.md',
                enforcement_level TEXT DEFAULT 'strict',
                auto_update_hub BOOLEAN DEFAULT TRUE,
                auto_create_hub BOOLEAN DEFAULT TRUE,
                status TEXT DEFAULT 'initializing',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_scan_at TIMESTAMP,
                scan_config TEXT DEFAULT '{}',
                total_files INTEGER DEFAULT 0,
                analyzed_files INTEGER DEFAULT 0,
                total_relationships INTEGER DEFAULT 0
            )
        """)
        
        # Create files table
        cursor.execute("""
            CREATE TABLE files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER REFERENCES projects(id),
                path TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                name TEXT NOT NULL,
                extension TEXT,
                size_bytes INTEGER,
                content_hash TEXT,
                encoding TEXT,
                mime_type TEXT,
                file_type TEXT,
                language TEXT,
                file_created_at TIMESTAMP,
                file_modified_at TIMESTAMP,
                first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_analyzed_at TIMESTAMP,
                status TEXT DEFAULT 'discovered',
                analysis_error TEXT,
                line_count INTEGER,
                has_cross_references BOOLEAN DEFAULT FALSE,
                is_hub_file BOOLEAN DEFAULT FALSE,
                imports TEXT DEFAULT '[]',
                exports TEXT DEFAULT '[]',
                functions TEXT DEFAULT '[]',
                classes TEXT DEFAULT '[]',
                cross_ref_header TEXT,
                required_reading TEXT DEFAULT '[]',
                file_metadata TEXT DEFAULT '{}'
            )
        """)
        
        # Create file_relationships table
        cursor.execute("""
            CREATE TABLE file_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file_id INTEGER REFERENCES files(id),
                target_file_id INTEGER REFERENCES files(id),
                relationship_type TEXT NOT NULL,
                strength REAL DEFAULT 1.0,
                confidence REAL DEFAULT 1.0,
                detected_by TEXT,
                detection_context TEXT,
                is_bidirectional BOOLEAN DEFAULT FALSE,
                is_required_reading BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_verified_at TIMESTAMP,
                relationship_metadata TEXT DEFAULT '{}'
            )
        """)
        
        # Create scan_sessions table
        cursor.execute("""
            CREATE TABLE scan_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER REFERENCES projects(id),
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                status TEXT DEFAULT 'running',
                files_discovered INTEGER DEFAULT 0,
                files_analyzed INTEGER DEFAULT 0,
                relationships_created INTEGER DEFAULT 0,
                errors_count INTEGER DEFAULT 0,
                peak_memory_mb REAL,
                duration_seconds REAL,
                scan_config_snapshot TEXT DEFAULT '{}'
            )
        """)
        
        # Create indexes for performance
        cursor.execute("CREATE INDEX idx_file_project_path ON files(project_id, relative_path)")
        cursor.execute("CREATE INDEX idx_file_type_lang ON files(file_type, language)")
        cursor.execute("CREATE INDEX idx_file_status ON files(status)")
        cursor.execute("CREATE INDEX idx_relationship_source ON file_relationships(source_file_id)")
        cursor.execute("CREATE INDEX idx_relationship_target ON file_relationships(target_file_id)")
        cursor.execute("CREATE INDEX idx_relationship_type ON file_relationships(relationship_type)")
        
        # Commit changes
        conn.commit()
        print(f"✅ SQLite database created successfully at: {db_path}")
        
        # Insert a default project
        cursor.execute("""
            INSERT INTO projects (name, root_path, status) 
            VALUES ('default', '/tmp', 'initialized')
        """)
        conn.commit()
        print("✅ Default project created")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    create_sqlite_database() 