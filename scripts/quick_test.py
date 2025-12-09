#!/usr/bin/env python3
"""
Quick Test Script for Content and Recommendations

This is a simpler version - just run it to see what's in your database!
"""

import asyncio
import json
import os
import sys
from datetime import datetime

import httpx

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

BASE_URL = "http://localhost:8000/api/v1"


async def quick_test():
    """Quick test to see content and recommendations."""

    print("🚀 Quick Content & Recommendations Test")
    print("=" * 50)

    # Login
    async with httpx.AsyncClient() as client:
        try:
            # Try to login
            login_response = await client.post(
                f"{BASE_URL}/auth/login",
                data={"username": "testuser", "password": "testpass123"},
            )

            if login_response.status_code == 200:
                token_data = login_response.json()
                token = token_data["access_token"]
                user_id = token_data.get("user_id", 1)
                headers = {"Authorization": f"Bearer {token}"}
                print(f"✅ Logged in as user {user_id}")
            else:
                print("❌ Login failed - using no auth")
                headers = {}
                user_id = 1

            print("\n📚 CONTENT IN DATABASE:")
            print("-" * 30)

            # Get content
            content_response = await client.get(f"{BASE_URL}/content/", headers=headers)

            if content_response.status_code == 200:
                content_list = content_response.json()

                if not content_list:
                    print("📭 No content found!")
                else:
                    for i, content in enumerate(content_list[:10], 1):
                        category_name = (
                            content.get("category", {}).get("name", "No Category")
                            if isinstance(content.get("category"), dict)
                            else "No Category"
                        )
                        print(f"{i}. [{content['id']}] {content['title']}")
                        print(
                            f"   Type: {content['content_type']} | Category: {category_name}"
                        )
                        if content.get("description"):
                            print(f"   Description: {content['description'][:100]}...")
                        print()
            else:
                print(f"❌ Could not fetch content: {content_response.text}")

            print("\n🎯 RECOMMENDATIONS TEST:")
            print("-" * 30)

            # Test different algorithms
            algorithms = ["auto", "trending_hot", "content_based"]

            for algorithm in algorithms:
                print(f"\n🤖 Testing {algorithm.upper()} algorithm:")
                try:
                    rec_response = await client.get(
                        f"{BASE_URL}/recommendations/user/{user_id}?algorithm={algorithm}&num_recommendations=3",
                        headers=headers,
                    )

                    if rec_response.status_code == 200:
                        rec_data = rec_response.json()
                        recommendations = rec_data.get("recommendations", [])

                        if recommendations:
                            for i, rec in enumerate(recommendations, 1):
                                score = rec.get("score", 0)
                                explanation = rec.get("explanation", {})
                                reason = explanation.get("reason", "No reason provided")

                                print(f"  {i}. {rec['title']} (Score: {score:.3f})")
                                print(f"     Reason: {reason}")
                        else:
                            print("     📭 No recommendations")

                        # Show algorithm info
                        algo_info = rec_data.get("algorithm_info", {})
                        if algo_info:
                            print(f"     Algorithm: {algo_info.get('name', 'Unknown')}")
                            print(
                                f"     Context: {algo_info.get('user_context', 'No context')}"
                            )
                    else:
                        print(f"     ❌ Error: {rec_response.text}")

                except Exception as e:
                    print(f"     ❌ Exception: {e}")

            print("\n" + "=" * 50)
            print("✅ Test completed!")
            print("\n💡 To explore more, run: python scripts/inspect_content.py")

        except Exception as e:
            print(f"❌ Connection error: {e}")
            print("Make sure your API server is running: docker-compose up")


if __name__ == "__main__":
    asyncio.run(quick_test())
