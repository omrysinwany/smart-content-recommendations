#!/bin/bash

# Simple Content & Recommendations Test Script
# No Python dependencies required - uses curl only

echo "🚀 Smart Content Recommendations Test"
echo "======================================="
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# API Configuration
BASE_URL="http://localhost:8000"
API_V1="$BASE_URL/api/v1"
TOKEN=""

# Function to print colored output
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "${CYAN}$1${NC}"
}

# Login function
login() {
    print_info "Attempting login..."
    
    RESPONSE=$(curl -s -X POST "$API_V1/auth/login" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=testuser&password=testpass123")
    
    if [[ $? -eq 0 ]]; then
        TOKEN=$(echo "$RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
        USER_ID=$(echo "$RESPONSE" | grep -o '"user_id":[0-9]*' | cut -d':' -f2)
        
        if [[ -n "$TOKEN" ]]; then
            print_success "Logged in! User ID: $USER_ID"
            return 0
        else
            print_warning "Login response: $RESPONSE"
            return 1
        fi
    else
        print_error "Could not connect to API"
        return 1
    fi
}

# Get content function
show_content() {
    print_header "📚 CONTENT IN DATABASE:"
    echo "------------------------"
    
    if [[ -n "$TOKEN" ]]; then
        HEADERS="Authorization: Bearer $TOKEN"
    else
        HEADERS=""
    fi
    
    CONTENT=$(curl -s -X GET "$API_V1/content/" -H "$HEADERS")
    
    if [[ $? -eq 0 ]]; then
        # Parse JSON and display nicely (basic parsing)
        echo "$CONTENT" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if isinstance(data, list):
        if not data:
            print('📭 No content found!')
        else:
            for i, item in enumerate(data[:10], 1):
                title = item.get('title', 'No title')[:60]
                content_type = item.get('content_type', 'unknown')
                cat_name = 'No Category'
                if isinstance(item.get('category'), dict):
                    cat_name = item['category'].get('name', 'No Category')
                print(f'{i}. [{item.get(\"id\", \"?\")}] {title}')
                print(f'   Type: {content_type} | Category: {cat_name}')
                desc = item.get('description', '')
                if desc:
                    print(f'   Description: {desc[:100]}...')
                print()
    else:
        print('Unexpected response format')
        print(data)
except Exception as e:
    print('Error parsing response:', e)
    print('Raw response:')
    print(sys.stdin.read())
" 2>/dev/null || echo "$CONTENT"
    else
        print_error "Could not fetch content"
    fi
}

# Test recommendations function
test_recommendations() {
    local algorithm=$1
    local user_id=${2:-1}
    
    print_header "🎯 Testing $algorithm algorithm (User $user_id):"
    
    if [[ -n "$TOKEN" ]]; then
        HEADERS="Authorization: Bearer $TOKEN"
    else
        HEADERS=""
    fi
    
    RECS=$(curl -s -X GET "$API_V1/recommendations/user/$user_id?algorithm=$algorithm&num_recommendations=3" -H "$HEADERS")
    
    if [[ $? -eq 0 ]]; then
        # Parse and display recommendations
        echo "$RECS" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    
    if 'recommendations' in data:
        recs = data['recommendations']
        if not recs:
            print('   📭 No recommendations found')
        else:
            for i, rec in enumerate(recs, 1):
                title = rec.get('title', 'No title')[:50]
                score = rec.get('score', 0)
                explanation = rec.get('explanation', {})
                reason = explanation.get('reason', 'No reason')
                
                print(f'   {i}. {title} (Score: {score:.3f})')
                print(f'      Reason: {reason}')
                
                factors = explanation.get('factors', [])
                if factors:
                    print(f'      Factors: {factors[0] if factors else \"None\"}')
    
    # Show algorithm info
    if 'algorithm_info' in data:
        algo_info = data['algorithm_info']
        print(f'   🤖 Algorithm: {algo_info.get(\"name\", \"Unknown\")}')
        print(f'   📊 Context: {algo_info.get(\"user_context\", \"Unknown\")}')
        
    # Show processing time if available
    if 'processing_time_ms' in data:
        print(f'   ⚡ Processing time: {data[\"processing_time_ms\"]:.1f}ms')
        
except Exception as e:
    print('   ❌ Error parsing recommendations:', e)
    print('   Raw response:')
    print(sys.stdin.read())
" 2>/dev/null || echo "   Raw response: $RECS"
    else
        print_error "Could not get recommendations for $algorithm"
    fi
    echo
}

# Main execution
main() {
    # Check if API is running
    print_info "Checking API health..."
    HEALTH=$(curl -s "$BASE_URL/health" 2>/dev/null)
    
    if [[ $? -ne 0 ]]; then
        print_error "API is not running at $BASE_URL"
        print_info "Start it with: docker-compose up"
        exit 1
    fi
    
    print_success "API is running!"
    echo
    
    # Try to login
    login
    echo
    
    # Show content
    show_content
    echo
    
    # Test different algorithms
    algorithms=("auto" "trending_hot" "content_based" "hybrid")
    
    for algo in "${algorithms[@]}"; do
        test_recommendations "$algo" "$USER_ID"
    done
    
    echo "======================================="
    print_success "Test completed!"
    print_info "For more detailed exploration, install Python packages:"
    print_info "pip install httpx rich"
    print_info "python3 scripts/inspect_content.py"
}

main "$@"
