#!/usr/bin/env python3
"""
Recommendation Tracker - See which algorithms recommended which content

This tool shows you:
1. Which content was recommended by which algorithm
2. User interactions with recommendations
3. Algorithm performance comparisons
4. Real-time recommendation tracking
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

try:
    import httpx
    from rich import box
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("❌ Required packages not installed. Install with:")
    print("pip install httpx rich")
    sys.exit(1)

console = Console()

# API Configuration
BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"


class RecommendationTracker:
    """Track and analyze recommendation algorithms in real-time."""

    def __init__(self):
        self.token = None
        self.user_id = None

    async def login(
        self, email: str = "test@example.com", password: str = "testpass123"
    ):
        """Login to get authentication token."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{API_V1}/auth/login", json={"email": email, "password": password}
                )
                if response.status_code == 200:
                    data = response.json()
                    self.token = data["access_token"]
                    self.user_id = data.get("user_id")
                    console.print(f"✅ Logged in successfully!")
                    return True
                else:
                    console.print(f"❌ Login failed: {response.text}")
                    return False
            except Exception as e:
                console.print(f"❌ Login error: {e}")
                return False

    def get_headers(self):
        """Get headers with authentication."""
        if not self.token:
            return None
        return {"Authorization": f"Bearer {self.token}"}

    async def get_recommendation_history(self, days_back: int = 7, limit: int = 50):
        """Get recent recommendation history."""
        headers = self.get_headers()
        if not headers:
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{API_V1}/analytics/recommendations/history",
                    params={"days_back": days_back, "limit": limit},
                    headers=headers,
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    console.print(f"❌ Failed to get history: {response.text}")
                    return None
            except Exception as e:
                console.print(f"❌ Error getting history: {e}")
                return None

    async def get_algorithm_performance(self, days_back: int = 7):
        """Get algorithm performance metrics."""
        headers = self.get_headers()
        if not headers:
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{API_V1}/analytics/algorithms/performance",
                    params={"days_back": days_back},
                    headers=headers,
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    console.print(f"❌ Failed to get performance: {response.text}")
                    return None
            except Exception as e:
                console.print(f"❌ Error getting performance: {e}")
                return None

    async def get_content_recommendations(self, content_id: int, days_back: int = 30):
        """Get recommendation history for specific content."""
        headers = self.get_headers()
        if not headers:
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{API_V1}/analytics/content/{content_id}/recommendations",
                    params={"days_back": days_back},
                    headers=headers,
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    console.print(f"❌ Failed to get content data: {response.text}")
                    return None
            except Exception as e:
                console.print(f"❌ Error getting content data: {e}")
                return None

    async def show_recommendation_history(self, days_back: int = 7):
        """Display recommendation history in a nice table."""
        data = await self.get_recommendation_history(days_back)
        if not data:
            return

        history = data.get("history", [])
        if not history:
            console.print("📭 No recommendation history found")
            return

        table = Table(
            title=f"📊 Recommendation History (Last {days_back} days)", box=box.ROUNDED
        )
        table.add_column("Time", style="cyan")
        table.add_column("User", style="green")
        table.add_column("Content", style="yellow")
        table.add_column("Algorithm", style="magenta")
        table.add_column("Score", style="blue")
        table.add_column("Position", style="red")
        table.add_column("Outcome", style="white")

        for rec in history[:20]:  # Show latest 20
            created_time = datetime.fromisoformat(
                rec["created_at"].replace("Z", "+00:00")
            )
            time_str = created_time.strftime("%m-%d %H:%M")

            outcome_color = {
                "shown": "white",
                "clicked": "green",
                "liked": "bright_green",
                "saved": "blue",
                "dismissed": "red",
            }.get(rec["outcome"], "white")

            table.add_row(
                time_str,
                rec["user_name"] or f"User {rec['user_id']}",
                rec["content_title"][:30]
                + ("..." if len(rec["content_title"]) > 30 else ""),
                rec["algorithm_name"],
                f"{rec['recommendation_score']:.3f}",
                str(rec["position"]),
                f"[{outcome_color}]{rec['outcome']}[/{outcome_color}]",
            )

        console.print(table)
        console.print(
            f"\\n💡 Showing {len(history[:20])} of {len(history)} total recommendations"
        )

    async def show_algorithm_performance(self, days_back: int = 7):
        """Display algorithm performance comparison."""
        data = await self.get_algorithm_performance(days_back)
        if not data:
            return

        algorithms = data.get("performance_summary", [])
        if not algorithms:
            console.print("📭 No algorithm performance data found")
            return

        table = Table(
            title=f"🤖 Algorithm Performance (Last {days_back} days)", box=box.ROUNDED
        )
        table.add_column("Algorithm", style="cyan")
        table.add_column("Total Recs", style="yellow")
        table.add_column("CTR %", style="green")
        table.add_column("Like %", style="blue")
        table.add_column("Save %", style="magenta")
        table.add_column("Engagement %", style="bright_green")
        table.add_column("Avg Score", style="white")
        table.add_column("Speed (ms)", style="red")

        for alg in algorithms:
            table.add_row(
                alg["algorithm_name"],
                str(alg["total_recommendations"]),
                f"{alg['click_through_rate']:.1f}%",
                f"{alg['like_rate']:.1f}%",
                f"{alg['save_rate']:.1f}%",
                f"{alg['engagement_rate']:.1f}%",
                f"{alg['avg_recommendation_score']:.3f}",
                f"{alg['avg_generation_time_ms']:.1f}",
            )

        console.print(table)

        # Show insights
        insights = data.get("insights", [])
        if insights:
            console.print("\\n💡 Key Insights:")
            for insight in insights:
                console.print(f"   • {insight}")

    async def show_content_analysis(self, content_id: int):
        """Show how different algorithms recommend specific content."""
        data = await self.get_content_recommendations(content_id)
        if not data:
            return

        content = data.get("content", {})
        stats = data.get("recommendation_stats", {})

        # Show content info
        content_info = f"""
📄 Content: {content.get('title', 'Unknown')}
📖 Type: {content.get('content_type', 'Unknown')}
🏷️  Category: {content.get('category', 'None')}
👀 Views: {content.get('view_count', 0)}
❤️  Likes: {content.get('like_count', 0)}
        """.strip()

        console.print(
            Panel(
                content_info,
                title=f"Content Analysis - ID: {content_id}",
                border_style="green",
            )
        )

        # Show algorithm stats
        algorithms = stats.get("algorithms", [])
        if algorithms:
            table = Table(title="Algorithm Recommendation Performance", box=box.ROUNDED)
            table.add_column("Algorithm", style="cyan")
            table.add_column("Times Recommended", style="yellow")
            table.add_column("Clicks", style="green")
            table.add_column("CTR %", style="blue")
            table.add_column("Avg Score", style="magenta")
            table.add_column("Avg Position", style="white")

            for alg in algorithms:
                table.add_row(
                    alg["algorithm_name"],
                    str(alg["times_recommended"]),
                    str(alg["clicks"]),
                    f"{alg['click_through_rate']:.1f}%",
                    f"{alg['avg_recommendation_score']:.3f}",
                    f"{alg['avg_position']:.1f}",
                )

            console.print(table)

        # Summary stats
        total_recs = stats.get("total_recommendations", 0)
        total_clicks = stats.get("total_clicks", 0)
        overall_ctr = stats.get("overall_ctr", 0)

        summary = f"📊 Total recommendations: {total_recs} | Total clicks: {total_clicks} | Overall CTR: {overall_ctr:.1f}%"
        console.print(f"\\n{summary}")

    async def generate_test_recommendations(self, user_id: int = None):
        """Generate some test recommendations to populate data."""
        headers = self.get_headers()
        if not headers:
            return

        if user_id is None:
            user_id = self.user_id or 1

        algorithms = ["trending_hot", "content_based", "hybrid", "auto"]

        console.print(f"🎯 Generating test recommendations for user {user_id}...")

        async with httpx.AsyncClient() as client:
            for algorithm in algorithms:
                try:
                    response = await client.get(
                        f"{API_V1}/recommendations/user/{user_id}",
                        params={"algorithm": algorithm, "num_recommendations": 3},
                        headers=headers,
                    )

                    if response.status_code == 200:
                        data = response.json()
                        recs = data.get("recommendations", [])
                        console.print(
                            f"✅ {algorithm}: Generated {len(recs)} recommendations"
                        )
                    else:
                        console.print(
                            f"❌ {algorithm}: Failed - {response.text[:100]}..."
                        )

                    await asyncio.sleep(0.5)  # Small delay between requests

                except Exception as e:
                    console.print(f"❌ {algorithm}: Error - {e}")

    async def interactive_menu(self):
        """Interactive menu for exploring recommendations."""
        while True:
            console.print(
                """
🔍 Recommendation Tracker - Main Menu
====================================

1. 📊 Show Recommendation History
2. 🤖 Show Algorithm Performance
3. 📄 Analyze Specific Content
4. 🎯 Generate Test Recommendations  
5. 🔄 Refresh Data
6. 📈 Live Performance Monitor
7. ❌ Exit

            """
            )

            choice = console.input("Enter choice (1-7): ").strip()

            try:
                if choice == "1":
                    days = console.input("Days back (default 7): ").strip()
                    days = int(days) if days else 7
                    await self.show_recommendation_history(days)

                elif choice == "2":
                    days = console.input("Days back (default 7): ").strip()
                    days = int(days) if days else 7
                    await self.show_algorithm_performance(days)

                elif choice == "3":
                    content_id = console.input("Content ID: ").strip()
                    if content_id:
                        await self.show_content_analysis(int(content_id))

                elif choice == "4":
                    user_id = console.input(
                        f"User ID (default {self.user_id or 1}): "
                    ).strip()
                    user_id = int(user_id) if user_id else (self.user_id or 1)
                    await self.generate_test_recommendations(user_id)

                elif choice == "5":
                    console.print("🔄 Refreshing data...")
                    # Just continue to next iteration

                elif choice == "6":
                    await self.live_monitor()

                elif choice == "7":
                    console.print("👋 Goodbye!")
                    break

                else:
                    console.print("❌ Invalid choice")

            except KeyboardInterrupt:
                console.print("\\n👋 Goodbye!")
                break
            except Exception as e:
                console.print(f"❌ Error: {e}")

    async def live_monitor(self):
        """Live monitoring of recommendation performance."""
        console.print("📈 Starting live monitor... Press Ctrl+C to stop")

        try:
            with Live(refresh_per_second=0.5) as live:
                while True:
                    # Get latest performance data
                    data = await self.get_algorithm_performance(days_back=1)

                    if data:
                        algorithms = data.get("performance_summary", [])

                        table = Table(
                            title="🔴 LIVE - Algorithm Performance (Last 24h)",
                            box=box.ROUNDED,
                        )
                        table.add_column("Algorithm", style="cyan")
                        table.add_column("Recommendations", style="yellow")
                        table.add_column("CTR %", style="green")
                        table.add_column("Engagement %", style="bright_green")
                        table.add_column("Avg Score", style="white")

                        for alg in algorithms:
                            table.add_row(
                                alg["algorithm_name"],
                                str(alg["total_recommendations"]),
                                f"{alg['click_through_rate']:.1f}%",
                                f"{alg['engagement_rate']:.1f}%",
                                f"{alg['avg_recommendation_score']:.3f}",
                            )

                        if algorithms:
                            live.update(table)
                        else:
                            live.update(Text("📭 No data available", style="yellow"))

                    await asyncio.sleep(5)  # Update every 5 seconds

        except KeyboardInterrupt:
            console.print("\\n📈 Live monitoring stopped")


async def main():
    """Main function."""
    tracker = RecommendationTracker()

    console.print(
        """
🔍 Smart Content Recommendations Tracker
========================================

This tool helps you track and analyze your recommendation algorithms!
    """
    )

    # Try to login
    console.print("🔐 Attempting login...")
    if not await tracker.login():
        console.print(
            "❌ Could not login. Make sure your API is running and you have the correct credentials."
        )
        return

    # Start interactive menu
    await tracker.interactive_menu()


if __name__ == "__main__":
    asyncio.run(main())
