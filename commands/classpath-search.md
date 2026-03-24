---
description: Search for a Java class across all Maven dependencies to find which JAR(s) contain it. Useful when you need to find the right import, resolve classpath conflicts, or discover which dependency provides a class. Accepts a fully qualified class name or a simple class name pattern.
---

Search for the Java class across project dependencies: $ARGUMENTS

## Instructions

1. **Determine the search pattern.** The argument can be:
   - A fully qualified class name like `com.fasterxml.jackson.databind.ObjectMapper` — convert to path: `com/fasterxml/jackson/databind/ObjectMapper.class`
   - A simple class name like `ObjectMapper` — search for any path ending in `/ObjectMapper.class`
   - A partial pattern like `jackson.ObjectMapper` — convert dots to path separators

2. **Use the pre-built class index for fast searching:**
   ```bash
   INDEX="$HOME/.claude/tools/class-index.txt"

   # Rebuild index if missing or older than 7 days
   if [ ! -f "$INDEX" ] || [ $(find "$INDEX" -mtime +7 2>/dev/null | wc -l) -gt 0 ]; then
     # Index build can take a while — dispatch it as a subagent using the Agent tool:
     # "Run: bash $HOME/.claude/tools/build-class-index.sh — report when done."
     # Wait for the subagent to complete before searching.
   fi

   # Search the index (instant — just a grep on a text file)
   grep -i "ClassName" "$INDEX"
   ```

   For a fully qualified name like `com.fasterxml.jackson.databind.ObjectMapper`:
   ```bash
   grep "com/fasterxml/jackson/databind/ObjectMapper\.class" "$INDEX"
   ```

   For a simple class name like `ObjectMapper`:
   ```bash
   grep -i "/ObjectMapper\.class" "$INDEX"
   ```

3. **Also check local build output** for project modules:
   ```bash
   find . -path "*/target/classes/*ClassName.class" 2>/dev/null
   ```

4. **Present results** showing:
   - The full path of each matching class within the JAR
   - The JAR file path (highlighting the groupId, artifactId, and version from the path)
   - If multiple versions exist, flag this as a potential classpath conflict
   - The Maven coordinates (groupId:artifactId:version) extracted from the JAR path

5. If no results are found:
   - Try rebuilding the index via a subagent: `bash "$HOME/.claude/tools/build-class-index.sh"`
   - Check spelling
   - The dependency might not be in the local repo — suggest `mvn dependency:resolve`
   - Try a broader search pattern

## Notes
- The index excludes inner classes (`$`), `module-info`, and `package-info` by default
- If you need inner classes, search the JAR directly: `jar tf /path/to.jar | grep ClassName`
- The index is built with 8 parallel workers and typically takes under 60 seconds
- Index is at `$HOME/.claude/tools/class-index.txt`
