#!/usr/bin/env python3
"""
Content Inspection Tool for Smart Content Recommendations

This tool helps you:
1. See all content in your database
2. Test recommendations for users
3. Understand why content was recommended
4. View user interactions
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import httpx
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

# API Configuration
BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"


class ContentInspector:
    """Inspect content and recommendations without a UI."""

    def __init__(self):
        self.token = None
        self.current_user_id = None

    async def login(self, username: str = "testuser", password: str = "testpass123"):
        """Login to get authentication token."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{API_V1}/auth/login",
                    data={"username": username, "password": password},
                )
                if response.status_code == 200:
                    data = response.json()
                    self.token = data["access_token"]
                    self.current_user_id = data.get("user_id")
                    console.print(f"✅ Logged in as: {username}")
                    return True
                else:
                    console.print(f"❌ Login failed: {response.text}")
                    return False
            except Exception as e:
                console.print(f"❌ Login error: {e}")
                return False

    def get_headers(self):
        """Get headers with authentication token."""
        if not self.token:
            console.print("❌ Not logged in. Run login() first.")
            return None
        return {"Authorization": f"Bearer {self.token}"}

    async def show_all_content(self, limit: int = 10):
        """Display all available content in a nice table."""
        headers = self.get_headers()
        if not headers:
            return

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{API_V1}/content/?limit={limit}", headers=headers
                )

                if response.status_code != 200:
                    console.print(f"❌ Failed to fetch content: {response.text}")
                    return

                content_list = response.json()

                if not content_list:
                    console.print("📭 No content found in database")
                    return

                # Create content table
                table = Table(title="📚 Available Content", box=box.ROUNDED)
                table.add_column("ID", style="cyan", no_wrap=True)
                table.add_column("Title", style="green")
                table.add_column("Type", style="yellow")
                table.add_column("Category", style="magenta")
                table.add_column("Created", style="blue")

                for content in content_list:
                    created_date = content.get("created_at", "Unknown")
                    if created_date != "Unknown":
                        try:
                            created_date = datetime.fromisoformat(
                                created_date.replace("Z", "+00:00")
                            )
                            created_date = created_date.strftime("%Y-%m-%d")
                        except:
                            pass

                    table.add_row(
                        str(content["id"]),
                        content["title"][:50]
                        + ("..." if len(content["title"]) > 50 else ""),
                        content["content_type"],
                        content.get("category", {}).get("name", "No Category"),
                        created_date,
                    )

                console.print(table)
                console.print(f"\n💡 Total content items: {len(content_list)}")

            except Exception as e:
                console.print(f"❌ Error fetching content: {e}")

    async def show_content_details(self, content_id: int):
        """Show detailed view of specific content."""
        headers = self.get_headers()
        if not headers:
            return

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{API_V1}/content/{content_id}", headers=headers
                )

                if response.status_code != 200:
                    console.print(f"❌ Content not found: {response.text}")
                    return

                content = response.json()

                # Create detailed panel
                details = f"""
📋 Title: {content['title']}
🏷️  Type: {content['content_type']}
📂 Category: {content.get('category', {}).get('name', 'No Category')}
📅 Created: {content.get('created_at', 'Unknown')}
📝 Description: {content.get('description', 'No description')[:200]}...
🏷️  Tags: {', '.join(content.get('tags', []))}
                """.strip()

                console.print(
                    Panel(
                        details,
                        title=f"Content Details - ID: {content_id}",
                        border_style="green",
                    )
                )

            except Exception as e:
                console.print(f"❌ Error fetching content details: {e}")

    async def test_recommendations(
        self, user_id: int = None, algorithm: str = "auto", num_recs: int = 5
    ):
        """Get and display recommendations for a user."""
        headers = self.get_headers()
        if not headers:
            return

        if user_id is None:
            user_id = self.current_user_id

        if user_id is None:
            console.print("❌ No user ID provided and not logged in")
            return

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{API_V1}/recommendations/user/{user_id}?algorithm={algorithm}&num_recommendations={num_recs}",
                    headers=headers,
                )

                if response.status_code != 200:
                    console.print(f"❌ Failed to get recommendations: {response.text}")
                    return

                data = response.json()
                recommendations = data.get("recommendations", [])

                if not recommendations:
                    console.print("📭 No recommendations found")
                    return

                # Display recommendations
                console.print(
                    f"\n🎯 Recommendations for User {user_id} using '{algorithm}' algorithm:"
                )

                table = Table(box=box.ROUNDED)
                table.add_column("Rank", style="cyan", no_wrap=True)
                table.add_column("Title", style="green")
                table.add_column("Score", style="yellow")
                table.add_column("Category", style="magenta")
                table.add_column("Reason", style="blue")

                for i, rec in enumerate(recommendations, 1):
                    score = f"{rec.get('score', 0):.3f}"
                    reason = rec.get("explanation", {}).get("reason", "No explanation")
                    category = rec.get("category", {}).get("name", "Unknown")

                    table.add_row(
                        str(i),
                        rec["title"][:40] + ("..." if len(rec["title"]) > 40 else ""),
                        score,
                        category,
                        reason[:50] + ("..." if len(reason) > 50 else ""),
                    )

                console.print(table)

                # Show algorithm info
                algorithm_info = data.get("algorithm_info", {})
                if algorithm_info:
                    info_text = f"""
🤖 Algorithm Used: {algorithm_info.get('name', 'Unknown')}
📊 User Context: {algorithm_info.get('user_context', 'No context')}
⚡ Processing Time: {data.get('processing_time_ms', 0):.1f}ms
                    """.strip()
                    console.print(
                        Panel(info_text, title="Algorithm Details", border_style="blue")
                    )

            except Exception as e:
                console.print(f"❌ Error getting recommendations: {e}")

    async def show_user_interactions(self, user_id: int = None):
        """Show user's interaction history."""
        if user_id is None:
            user_id = self.current_user_id

        if user_id is None:
            console.print("❌ No user ID provided")
            return

        headers = self.get_headers()
        if not headers:
            return

        async with httpx.AsyncClient() as client:
            try:
                # This endpoint might not exist yet, so let's create a simple version
                console.print(f"👤 User {user_id} Interaction History:")
                console.print("(This feature requires additional API endpoint)")

            except Exception as e:
                console.print(f"❌ Error fetching interactions: {e}")

    async def compare_algorithms(self, user_id: int = None):
        """Compare different algorithms for the same user."""
        if user_id is None:
            user_id = self.current_user_id

        if user_id is None:
            console.print("❌ No user ID provided")
            return

        algorithms = [
            "content_based",
            "collaborative",
            "trending_hot",
            "hybrid",
            "auto",
        ]

        console.print(f"\n🔍 Comparing algorithms for User {user_id}:")

        for algorithm in algorithms:
            console.print(f"\n--- {algorithm.upper()} ---")
            await self.test_recommendations(user_id, algorithm, 3)
            await asyncio.sleep(0.5)  # Small delay between requests


async def main():
    """Interactive content inspection tool."""
    inspector = ContentInspector()

    console.print(
        """
🔍 Smart Content Recommendations Inspector
=========================================

This tool helps you explore your content and test recommendations!
    """
    )

    # Try to login
    console.print("🔐 Attempting login...")
    if not await inspector.login():
        console.print(
            "❌ Could not login. Make sure your API is running and you have a test user."
        )
        return

    while True:
        console.print(
            """
📋 Available Commands:
1. Show all content
2. Show content details (by ID)
3. Test recommendations
4. Compare algorithms
5. Show user interactions
6. Exit

        """
        )

        choice = input("Enter choice (1-6): ").strip()

        try:
            if choice == "1":
                limit = input("Number of items to show (default 10): ").strip()
                limit = int(limit) if limit else 10
                await inspector.show_all_content(limit)

            elif choice == "2":
                content_id = input("Enter content ID: ").strip()
                if content_id:
                    await inspector.show_content_details(int(content_id))

            elif choice == "3":
                user_id = input(
                    f"User ID (default: {inspector.current_user_id}): "
                ).strip()
                algorithm = input(
                    "Algorithm (auto/content_based/collaborative/trending_hot/hybrid): "
                ).strip()
                num_recs = input("Number of recommendations (default 5): ").strip()

                user_id = int(user_id) if user_id else inspector.current_user_id
                algorithm = algorithm if algorithm else "auto"
                num_recs = int(num_recs) if num_recs else 5

                await inspector.test_recommendations(user_id, algorithm, num_recs)

            elif choice == "4":
                user_id = input(
                    f"User ID (default: {inspector.current_user_id}): "
                ).strip()
                user_id = int(user_id) if user_id else inspector.current_user_id
                await inspector.compare_algorithms(user_id)

            elif choice == "5":
                user_id = input(
                    f"User ID (default: {inspector.current_user_id}): "
                ).strip()
                user_id = int(user_id) if user_id else inspector.current_user_id
                await inspector.show_user_interactions(user_id)

            elif choice == "6":
                console.print("👋 Goodbye!")
                break

            else:
                console.print("❌ Invalid choice")

        except KeyboardInterrupt:
            console.print("\n👋 Goodbye!")
            break
        except Exception as e:
            console.print(f"❌ Error: {e}")


if __name__ == "__main__":
    # Install required packages
    try:
        import httpx
        import rich
    except ImportError:
        console.print("📦 Installing required packages...")
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "rich", "httpx"])
        import httpx
        import rich

        console.print("✅ Packages installed!")

    asyncio.run(main())
