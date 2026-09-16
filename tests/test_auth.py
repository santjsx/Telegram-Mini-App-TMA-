import pytest
import os
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path

from app.auth.manager import AccessManager, UserInfo, RequestInfo
from app.commands.admin import AdminCommandHandler
from app.commands.router import CommandRouter
from app.config import Config


@pytest.fixture
def temp_access_file(tmp_path):
    return str(tmp_path / "access_control.json")


def test_access_manager_init(temp_access_file):
    manager = AccessManager(
        admin_id=1001,
        persistence_path=temp_access_file,
        initial_approved_ids=(2001, 2002),
    )
    assert manager.is_admin(1001) is True
    assert manager.is_admin(2001) is False
    assert manager.is_authorized(1001) is True
    assert manager.is_authorized(2001) is True
    assert manager.is_authorized(2002) is True
    assert manager.is_authorized(9999) is False


@pytest.mark.asyncio
async def test_access_manager_request_and_approval(temp_access_file):
    manager = AccessManager(admin_id=1001, persistence_path=temp_access_file)

    # 1. New request
    is_new, req = await manager.add_request(
        user_id=5001,
        first_name="Alice",
        last_name="Smith",
        username="alicesmith",
    )
    assert is_new is True
    assert req.user_id == 5001
    assert req.display_name == "Alice Smith"
    assert req.mention == "@alicesmith"
    assert manager.is_pending(5001) is True
    assert manager.is_authorized(5001) is False

    # 2. Duplicate request
    is_new2, req2 = await manager.add_request(user_id=5001, first_name="Alice")
    assert is_new2 is False
    assert len(manager.get_all_pending()) == 1

    # 3. Approve user
    user = await manager.approve_user(5001, approved_by=1001)
    assert user is not None
    assert user.user_id == 5001
    assert manager.is_authorized(5001) is True
    assert manager.is_pending(5001) is False

    # 4. Verify persistence
    reloaded = AccessManager(admin_id=1001, persistence_path=temp_access_file)
    assert reloaded.is_authorized(5001) is True
    assert reloaded.get_user(5001).display_name == "Alice Smith"


@pytest.mark.asyncio
async def test_access_manager_denial_and_revocation(temp_access_file):
    manager = AccessManager(admin_id=1001, persistence_path=temp_access_file)

    # Deny pending request
    await manager.add_request(user_id=6001, first_name="Bob")
    assert manager.is_pending(6001) is True
    denied = await manager.deny_user(6001)
    assert denied is not None
    assert manager.is_pending(6001) is False
    assert manager.is_authorized(6001) is False

    # Revoke approved user
    await manager.approve_user(7001, approved_by=1001)
    assert manager.is_authorized(7001) is True
    revoked = await manager.revoke_user(7001)
    assert revoked is True
    assert manager.is_authorized(7001) is False

    # Admin cannot be revoked
    admin_revoked = await manager.revoke_user(1001)
    assert admin_revoked is False
    assert manager.is_authorized(1001) is True


@pytest.mark.asyncio
async def test_admin_handler_unauthorized_message(temp_access_file):
    manager = AccessManager(admin_id=1001, persistence_path=temp_access_file)
    handler = AdminCommandHandler(
        indexer=MagicMock(),
        user_client=MagicMock(),
        config=MagicMock(authorized_user_id=1001),
        access_manager=manager,
    )

    mock_msg = MagicMock()
    mock_msg.sender_id = 9999
    mock_msg.reply = AsyncMock()

    # First time -> show request access button
    await handler.handle_unauthorized_message(mock_msg)
    mock_msg.reply.assert_called_once()
    call_args = mock_msg.reply.call_args
    assert "Private Music Cloud" in call_args[0][0]
    assert call_args[1]["buttons"] is not None

    # After requesting -> show pending message
    await manager.add_request(9999, first_name="PendingUser")
    mock_msg.reply.reset_mock()
    await handler.handle_unauthorized_message(mock_msg)
    assert "Access Request Pending" in mock_msg.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_admin_handler_request_access_and_approval_flow(temp_access_file):
    manager = AccessManager(admin_id=1001, persistence_path=temp_access_file)
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    handler = AdminCommandHandler(
        indexer=MagicMock(),
        user_client=MagicMock(),
        config=MagicMock(authorized_user_id=1001),
        access_manager=manager,
        bot_manager=mock_bot,
    )

    # 1. User clicks "Request Access"
    mock_event = MagicMock()
    mock_event.sender_id = 8888
    mock_event.get_sender = AsyncMock(return_value=MagicMock(first_name="Charlie", last_name="Brown", username="cbrown"))
    mock_event.edit = AsyncMock()
    mock_event.answer = AsyncMock()

    await handler.handle_request_access_callback(mock_event)
    assert manager.is_pending(8888) is True
    mock_event.edit.assert_called_once()
    assert "Request Submitted" in mock_event.edit.call_args[0][0]
    mock_bot.send_message.assert_called_once()
    # Admin was notified with approve/deny buttons
    admin_call = mock_bot.send_message.call_args
    assert admin_call[0][0] == 1001
    assert "Charlie Brown" in admin_call[0][1]

    # 2. Admin approves user
    admin_event = MagicMock()
    admin_event.sender_id = 1001
    admin_event.data = b"auth:app:8888"
    admin_event.edit = AsyncMock()
    admin_event.answer = AsyncMock()

    mock_bot.send_message.reset_mock()
    await handler.handle_auth_callback(admin_event)
    assert manager.is_authorized(8888) is True
    admin_event.edit.assert_called_once()
    assert "Access Granted" in admin_event.edit.call_args[0][0]
    # User was welcomed in DM
    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args[0][0] == 8888
    assert "Access Granted" in mock_bot.send_message.call_args[0][1]


@pytest.mark.asyncio
async def test_admin_handler_revoke_flow(temp_access_file):
    manager = AccessManager(admin_id=1001, persistence_path=temp_access_file)
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    handler = AdminCommandHandler(
        indexer=MagicMock(),
        user_client=MagicMock(),
        config=MagicMock(authorized_user_id=1001),
        access_manager=manager,
        bot_manager=mock_bot,
    )

    await manager.approve_user(8888, approved_by=1001)

    # Admin revokes via callback
    admin_event = MagicMock()
    admin_event.sender_id = 1001
    admin_event.data = b"auth:rev:8888"
    admin_event.edit = AsyncMock()
    admin_event.answer = AsyncMock()

    await handler.handle_auth_callback(admin_event)
    assert manager.is_authorized(8888) is False
    assert "Access Revoked" in admin_event.edit.call_args[0][0]
    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args[0][0] == 8888


@pytest.mark.asyncio
async def test_admin_command_gating_in_router(temp_access_file):
    manager = AccessManager(admin_id=1001, persistence_path=temp_access_file)
    await manager.approve_user(2002, approved_by=1001)

    mock_status = MagicMock()
    mock_search = MagicMock()
    mock_download = MagicMock()
    mock_admin = MagicMock()
    mock_admin.handle_reindex = AsyncMock()
    mock_admin.handle_users = AsyncMock()

    router = CommandRouter(
        status_handler=mock_status,
        search_handler=mock_search,
        download_handler=mock_download,
        admin_handler=mock_admin,
        access_manager=manager,
    )

    # 1. Non-admin regular user attempts /reindex -> blocked
    user_msg = MagicMock()
    user_msg.text = "/reindex confirm"
    user_msg.sender_id = 2002
    user_msg.reply = AsyncMock()

    await router.route_message(user_msg)
    user_msg.reply.assert_called_once()
    assert "reserved for the bot administrator" in user_msg.reply.call_args[0][0]
    mock_admin.handle_reindex.assert_not_called()

    # 2. Non-admin regular user attempts /users -> blocked
    user_msg.text = "/users"
    user_msg.reply.reset_mock()
    await router.route_message(user_msg)
    assert "reserved for the bot administrator" in user_msg.reply.call_args[0][0]
    mock_admin.handle_users.assert_not_called()

    # 3. Admin runs /users -> allowed
    admin_msg = MagicMock()
    admin_msg.text = "/users"
    admin_msg.sender_id = 1001
    admin_msg.reply = AsyncMock()

    await router.route_message(admin_msg)
    mock_admin.handle_users.assert_called_once_with(admin_msg)
