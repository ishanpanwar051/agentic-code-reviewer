#include <iostream>
#include <sqlite3.h>
#include <cstdlib>
#include <cstring>

// Hardcoded secret -> CWE-798
const char* API_KEY = "sk_live_1234567890abcdef";

void search_user(const char* username, sqlite3* db) {
    char query[512];
    // SQL Injection via sprintf -> should be CWE-89 (prepared statement fix)
    sprintf(query, "SELECT * FROM users WHERE name = '%s'", username);
    sqlite3_exec(db, query, nullptr, nullptr, nullptr);
}

void copy_data(const char* input) {
    // Buffer overflow -> CWE-120
    char buffer[16];
    strcpy(buffer, input);
}

void run_command(const char* cmd) {
    // OS Command Injection -> CWE-78
    system(cmd);
}

void process(int amount) {
    try {
        int x = 100 / amount;
    } catch (...) {   // bare catch -> CWE-391
        // silently swallow
    }
}
