# malicious_zips

TASK-104 的恶意 zip fixture 构造脚本。测试运行时会在 pytest 临时目录生成 zip,
仓库不保存生成后的二进制压缩包。

## 重新生成

```bash
python tests/fixtures/malicious_zips/build_fixtures.py /tmp/mxa-malicious-zips
```

## 风险族矩阵

| 文件 | 构造目标 | 预期拒绝 |
|------|----------|----------|
| `zip_bomb_ratio.zip` | 2MB 高压缩比 `.m` payload | `ZipBombError` |
| `zip_slip_paths.zip` | `../escape.m` 路径穿越 | `ZipSlipError` |
| `symlink_chain.zip` | Unix symlink entry + 后续 payload | `ZipSlipError` |
| `duplicate_collision.zip` | 原始重复、NFC 碰撞、大小写碰撞 | `ZipSlipError` |
| `forbidden_type.zip` | `.mexw64` 黑名单扩展 | `FileTypeNotAllowedError` |
| `encrypted_or_bad_method.zip` | BZIP2 压缩方法 | `ZipBombError` |
| `total_uncompressed_exceeds_cap.zip` | 小型随机数据,测试时降低总解压阈值触发 | `ZipBombError` |
