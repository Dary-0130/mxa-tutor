# Malicious document fixtures

This directory is reserved for TASK-501 document-upload security fixtures.

TASK-500 only creates the directory marker. Actual binary fixtures must be added by a later
task together with tests for:

- encrypted PDFs
- PDFs with embedded JavaScript
- oversized PDFs
- docx files containing macros
- zip-bomb-style docx containers
- corrupted docx files

Document parsers must reject or safely downgrade these cases without executing embedded content,
opening network resources, or persisting raw document text.
