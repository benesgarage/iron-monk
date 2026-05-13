# Filesystem

## `IsDir`
`IsDir(*, message=None, code=None)` — `str` or `pathlib.Path` pointing to an existing directory.

## `IsFile`
`IsFile(*, message=None, code=None)` — `str` or `pathlib.Path` pointing to an existing file.

```python
config: Annotated[pathlib.Path, IsFile]
```

For validating uploaded-file bodies as raw bytes (size + magic-byte sniffing), see **[File Uploads](uploads.md)**.
