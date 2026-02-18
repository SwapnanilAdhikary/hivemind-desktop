from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, update

from app.db.database import async_session
from app.db.models import Tool
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)


class ToolRegistry:
    """DB-backed dynamic tool registry. Tools persist across sessions."""

    async def register(
        self,
        name: str,
        description: str,
        source_code: str,
        parameters_schema: dict | None = None,
    ) -> int:
        async with async_session() as session:
            existing = await session.execute(select(Tool).where(Tool.name == name))
            row = existing.scalar_one_or_none()
            if row:
                row.description = description
                row.source_code = source_code
                row.parameters_schema = parameters_schema or {}
                await session.commit()
                tool_id = row.id
                logger.info("Updated tool: %s (id=%d)", name, tool_id)
            else:
                row = Tool(
                    name=name,
                    description=description,
                    source_code=source_code,
                    parameters_schema=parameters_schema or {},
                )
                session.add(row)
                await session.commit()
                await session.refresh(row)
                tool_id = row.id
                logger.info("Registered new tool: %s (id=%d)", name, tool_id)

        await ws_manager.broadcast("tool_created", {
            "id": tool_id,
            "name": name,
            "description": description,
        })
        return tool_id

    async def get_tool(self, name: str) -> Tool | None:
        async with async_session() as session:
            result = await session.execute(select(Tool).where(Tool.name == name))
            return result.scalar_one_or_none()

    async def list_tools(self, enabled_only: bool = True) -> list[dict[str, Any]]:
        async with async_session() as session:
            stmt = select(Tool)
            if enabled_only:
                stmt = stmt.where(Tool.enabled == True)
            result = await session.execute(stmt)
            tools = result.scalars().all()
            return [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "parameters_schema": t.parameters_schema,
                    "usage_count": t.usage_count,
                    "enabled": t.enabled,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in tools
            ]

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a registered tool by name in a sandboxed namespace."""
        tool = await self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool not found: {name}")
        if not tool.enabled:
            raise ValueError(f"Tool is disabled: {name}")

        namespace: dict[str, Any] = {"__builtins__": __builtins__}
        exec(tool.source_code, namespace)

        func = namespace.get(name)
        if not callable(func):
            raise ValueError(f"Tool source does not define callable '{name}'")

        async with async_session() as session:
            await session.execute(
                update(Tool).where(Tool.name == name).values(usage_count=Tool.usage_count + 1)
            )
            await session.commit()

        result = func(**arguments)
        return result

    async def delete_tool(self, name: str) -> bool:
        async with async_session() as session:
            tool = await session.execute(select(Tool).where(Tool.name == name))
            row = tool.scalar_one_or_none()
            if row:
                await session.delete(row)
                await session.commit()
                return True
            return False

    async def toggle_tool(self, name: str, enabled: bool) -> bool:
        async with async_session() as session:
            result = await session.execute(
                update(Tool).where(Tool.name == name).values(enabled=enabled)
            )
            await session.commit()
            return result.rowcount > 0


tool_registry = ToolRegistry()
