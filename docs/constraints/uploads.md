# File Uploads

For validating uploaded-file bodies as raw `bytes` / `bytearray`. Designed to compose — stack on a single field via `Annotated`, or apply independently. Reads only the leading bytes, so memory cost is the file size you already loaded.

## `FileSize`
`FileSize(min_size=None, max_size=None, *, message=None, code=None)` — length check on `bytes` / `bytearray` payloads. Both bounds inclusive; either can be omitted. Does **not** accept `str` (use [`MaxBytes`](strings.md#maxbytes) for UTF-8 byte-length on strings).

```python
body: Annotated[bytes, FileSize(max_size=5_000_000)]
```

## `MagicBytes`
`MagicBytes(allowed=None, extra_signatures=None, *, message=None, code=None)` — sniffs the leading bytes of a `bytes` / `bytearray` payload against an internal registry of file-format signatures and asserts the detected mime is in `allowed`. Defends against extension- and `Content-Type`-header spoofing (a `.png` upload that's actually an executable will fail).

Built-in signatures cover:

| Family   | Mime types |
|----------|------------|
| Images   | `image/png`, `image/jpeg`, `image/gif`, `image/webp`, `image/bmp`, `image/tiff`, `image/x-icon` |
| Documents | `application/pdf`, `application/rtf` |
| Archives | `application/zip` (also matches DOCX/XLSX/PPTX), `application/gzip`, `application/x-tar`, `application/x-7z-compressed`, `application/vnd.rar` |
| Media    | `audio/mpeg`, `video/mp4`, `audio/wav`, `audio/ogg`, `video/webm`, `video/x-msvideo` |

When `allowed=None`, any recognized format passes — useful for "must be some known binary format" checks. Pass `extra_signatures={"custom/mime": ((b"\\x00...", 0),)}` to register additional formats; each entry maps a mime to an AND-pattern of `(bytes, offset)` pairs.

```python
avatar: Annotated[bytes, MagicBytes(allowed=("image/png", "image/jpeg")), FileSize(max_size=2_000_000)]
```

OOXML formats (DOCX, XLSX, PPTX) are matched as `application/zip` — they are ZIP archives at the byte level. Disambiguation requires parsing the ZIP central directory, which is out of scope.

[`MimeType`](format.md#mimetype) validates the **string format** of a claimed mime header; `MagicBytes` validates the **actual content** of a file body. They compose naturally on separate fields.
