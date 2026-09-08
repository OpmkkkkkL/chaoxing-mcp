"""两阶段确认门测试。"""

import pytest

from cxmcp.confirm import ConfirmationStore
from cxmcp.exceptions import ConfirmationRejected, ConfirmationRequired


def make_params():
    return {"courseId": 123, "title": "通知A"}


def test_issue_raises_with_token():
    store = ConfirmationStore()
    with pytest.raises(ConfirmationRequired) as ei:
        store.issue("send_notice", make_params(), "将发送通知")
    assert ei.value.token and ei.value.expires_in == 300


def test_consume_ok_and_replay_blocked():
    store = ConfirmationStore()
    with pytest.raises(ConfirmationRequired) as ei:
        store.issue("send_notice", make_params(), "x")
    token = ei.value.token
    store.consume("send_notice", make_params(), token)  # 第一次核销成功
    with pytest.raises(ConfirmationRejected):
        store.consume("send_notice", make_params(), token)  # 重放被拒


def test_param_change_invalidates_token():
    store = ConfirmationStore()
    with pytest.raises(ConfirmationRequired) as ei:
        store.issue("send_notice", make_params(), "x")
    with pytest.raises(ConfirmationRejected):
        store.consume("send_notice", {"courseId": 123, "title": "通知B"}, ei.value.token)


def test_wrong_token_rejected():
    store = ConfirmationStore()
    with pytest.raises(ConfirmationRequired):
        store.issue("a", {}, "x")
    with pytest.raises(ConfirmationRejected):
        store.consume("a", {}, "wrong-token")
