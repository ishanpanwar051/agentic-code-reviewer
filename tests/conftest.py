"""Pytest fixtures for PR Sage test suite."""

import pytest


@pytest.fixture
def diff_single_hunk() -> str:
    """Unified diff with a single hunk modifying existing lines."""
    return """diff --git a/src/calculator.py b/src/calculator.py
index e69de29..d95f3ad 100644
--- a/src/calculator.py
+++ b/src/calculator.py
@@ -10,5 +10,6 @@ def add(a: int, b: int) -> int:
     # Add two numbers safely
     return a + b
 
+def multiply(a: int, b: int) -> int:
+    return a * b
"""


@pytest.fixture
def diff_multi_hunk() -> str:
    """Unified diff with multiple hunks in one file."""
    return """diff --git a/src/service.py b/src/service.py
index a1b2c3d..e5f6a7b 100644
--- a/src/service.py
+++ b/src/service.py
@@ -1,4 +1,5 @@
 import os
+import sys
 
 def init():
     pass
@@ -20,6 +21,8 @@ def run():
     print("running")
-    return 0
+    # Updated return code logic
+    return 1
"""


@pytest.fixture
def diff_new_file() -> str:
    """Unified diff for a newly created file (old lines 0, new lines 5)."""
    return """diff --git a/src/new_module.py b/src/new_module.py
new file mode 100644
index 0000000..f1e2d3c
--- /dev/null
+++ b/src/new_module.py
@@ -0,0 +1,5 @@
+'''A newly added module.'''
+
+def hello():
+    return 'world'
+
"""


@pytest.fixture
def diff_deleted_file() -> str:
    """Unified diff for a deleted file."""
    return """diff --git a/legacy.py b/legacy.py
deleted file mode 100644
index f1e2d3c..0000000
--- a/legacy.py
+++ /dev/null
@@ -1,3 +0,0 @@
-def old():
-    pass
-
"""


@pytest.fixture
def diff_binary_file() -> str:
    """Unified diff for a binary asset."""
    return """diff --git a/assets/logo.png b/assets/logo.png
index 0000000..1111111 100644
Binary files a/assets/logo.png and b/assets/logo.png differ
"""


@pytest.fixture
def diff_rename_100() -> str:
    """Unified diff for a 100% rename without code changes."""
    return """diff --git a/old_name.py b/new_name.py
similarity index 100%
rename from old_name.py
rename to new_name.py
"""


@pytest.fixture
def diff_no_newline() -> str:
    """Unified diff with '\ No newline at end of file' marker."""
    return r"""diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -1,2 +1,2 @@
-print('old')
\ No newline at end of file
+print('new')
\ No newline at end of file
"""


@pytest.fixture
def diff_skip_paths() -> str:
    """Unified diff touching ignored assets like package-lock.json and dist bundle."""
    return """diff --git a/package-lock.json b/package-lock.json
index 111..222 100644
--- a/package-lock.json
+++ b/package-lock.json
@@ -1,3 +1,3 @@
 {
-  "version": "1.0.0"
+  "version": "1.0.1"
 }
diff --git a/dist/bundle.min.js b/dist/bundle.min.js
index 333..444 100644
--- a/dist/bundle.min.js
+++ b/dist/bundle.min.js
@@ -1,1 +1,1 @@
-var a=1;
+var a=2;
"""
