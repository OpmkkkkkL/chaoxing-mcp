"""AES 登录加密往返测试。"""

from cxmcp.crypto import decrypt_aes, encrypt_aes


def test_roundtrip():
    for s in ["13800138000", "p@ssw0rd 中文✓", "a" * 100, ""]:
        assert decrypt_aes(encrypt_aes(s)) == s


def test_known_key():
    # 固定密钥 & IV 应产生确定性密文
    c1, c2 = encrypt_aes("hello"), encrypt_aes("hello")
    assert c1 == c2 and c1 != "hello"
