#!/usr/bin/env python3
"""
Quick script to check actual database schema
"""
import sqlite3
import os

# Path to database
db_path = "data/invoices.db"

if os.path.exists(db_path):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        print("=== DATABASE SCHEMA ===")
        
        for table in tables:
            print(f"\nTable: {table}")
            print("-" * 30)
            
            # Get column info
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            
            for col in columns:
                print(f"  {col[1]} ({col[2]}) {'PRIMARY KEY' if col[5] else ''}")
        
        print("\n=== SAMPLE DATA ===")
        
        # Show sample data from invoices table
        cursor.execute("SELECT * FROM invoices LIMIT 1")
        row = cursor.fetchone()
        if row:
            cursor.execute("SELECT name FROM PRAGMA_TABLE_INFO('invoices')")
            columns = [col[0] for col in cursor.fetchall()]
            print(f"\nSample row from invoices:")
            for i, col in enumerate(columns):
                print(f"  {col}: {row[i]}")
else:
    print("Database not found at", db_path)