"""Run the MCP scraper server."""

from app.mcp.scraper_server import create_mcp_server


def main():
    """Run the MCP server."""
    server = create_mcp_server()

    # Run with stdio transport by default (for MCP protocol)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
