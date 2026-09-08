"""学习通登录页 AES-CBC 加密。

登录页 passport2.chaoxing.com 的隐藏域 t=true 时，uname/password 需用
固定密钥 TRANSFER_KEY 做 AES-CBC（IV 取密钥前 16 字节，PKCS#7，base64）。
"""

from __future__ import annotations

import base64

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

TRANSFER_KEY = b"u2oh6Vu^HWe4_AES"  # 学习通登录页内置的固定传输密钥（16 字节）


def encrypt_aes(plaintext: str) -> str:
    cipher = AES.new(TRANSFER_KEY, AES.MODE_CBC, IV=TRANSFER_KEY[:16])
    data = pad(plaintext.encode("utf-8"), AES.block_size)
    return base64.b64encode(cipher.encrypt(data)).decode("ascii")


def decrypt_aes(ciphertext_b64: str) -> str:
    cipher = AES.new(TRANSFER_KEY, AES.MODE_CBC, IV=TRANSFER_KEY[:16])
    raw = base64.b64decode(ciphertext_b64)
    return unpad(cipher.decrypt(raw), AES.block_size).decode("utf-8")
