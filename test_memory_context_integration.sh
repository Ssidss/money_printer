#!/bin/bash
# Integration test script for memory-context endpoint

BASE_URL="http://localhost:8000"
API_PREFIX="/api/v1"

echo "=== Testing memory-context endpoint ==="
echo ""

# Test 1: Query with valid params (empty data)
echo "Test 1: Query memory-context with no data"
curl -X GET \
  "${BASE_URL}${API_PREFIX}/ai-notes/memory-context?smc_trend=上升趨勢&recommendation_hint=推薦" \
  -H "Content-Type: application/json" \
  -w "\nHTTP Status: %{http_code}\n" \
  -s | python3 -m json.tool
echo ""

# Test 2: Verify response structure
echo "Test 2: Verify response contains required fields"
curl -X GET \
  "${BASE_URL}${API_PREFIX}/ai-notes/memory-context?smc_trend=盤整&recommendation_hint=觀察" \
  -H "Content-Type: application/json" \
  -s | python3 -c "
import sys, json
data = json.load(sys.stdin)
required_fields = ['has_memory', 'confidence_adjustment', 'warnings', 'historical_pattern', 'context_summary']
missing = [f for f in required_fields if f not in data]
if missing:
    print(f'❌ Missing fields: {missing}')
    sys.exit(1)
else:
    print('✅ All required fields present')
    print(f'  - has_memory: {data[\"has_memory\"]}')
    print(f'  - confidence_adjustment: {data[\"confidence_adjustment\"]}')
    print(f'  - warnings: {len(data[\"warnings\"])} warning(s)')
"
echo ""

# Test 3: Strategy-memory endpoint for reference
echo "Test 3: Check strategy-memory endpoint (reference)"
curl -X GET \
  "${BASE_URL}${API_PREFIX}/ai-notes/strategy-memory" \
  -H "Content-Type: application/json" \
  -w "\nHTTP Status: %{http_code}\n" \
  -s | python3 -m json.tool | head -30
