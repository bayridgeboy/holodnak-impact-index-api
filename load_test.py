#!/usr/bin/env python3
"""Simple load test for HII API"""
import requests
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

API_URL = "https://humanimpactindex.com/hii"
CACHE_STATS_URL = "https://humanimpactindex.com/cache-stats"

# Test data - mix of duplicate and unique queries
TEST_QUERIES = [
    ["Elon Musk"],
    ["Bill Gates"],
    ["Elon Musk"],  # Duplicate - should hit cache
    ["Jeff Bezos"],
    ["Elon Musk"],  # Another duplicate
    ["Tim Cook"],
    ["Bill Gates"],  # Duplicate
    ["Mark Zuckerberg"],
    ["Elon Musk"],  # Yet another duplicate
    ["Satya Nadella"],
]

def make_request(names, request_num):
    """Make a single HII request"""
    payload = {
        "people": [{"name": name} for name in names],
        "rubric_version": "impact_v1",
        "refresh": False
    }
    
    start = time.time()
    try:
        response = requests.post(API_URL, json=payload, timeout=30)
        duration = time.time() - start
        
        if response.status_code == 200:
            return {
                "request_num": request_num,
                "names": names,
                "status": "success",
                "duration": duration,
                "status_code": response.status_code
            }
        else:
            return {
                "request_num": request_num,
                "names": names,
                "status": "error",
                "duration": duration,
                "status_code": response.status_code,
                "error": response.text[:200]
            }
    except Exception as e:
        duration = time.time() - start
        return {
            "request_num": request_num,
            "names": names,
            "status": "exception",
            "duration": duration,
            "error": str(e)
        }

def run_load_test(concurrent_workers=3):
    """Run load test with specified concurrency"""
    print(f"\n{'='*60}")
    print(f"HII Load Test - {len(TEST_QUERIES)} requests, {concurrent_workers} concurrent workers")
    print(f"{'='*60}\n")
    
    # Get initial cache stats
    try:
        initial_stats = requests.get(CACHE_STATS_URL).json()
        print(f"Initial cache stats: {json.dumps(initial_stats, indent=2)}\n")
    except:
        print("Could not fetch initial cache stats\n")
    
    start_time = time.time()
    results = []
    
    # Execute requests concurrently
    with ThreadPoolExecutor(max_workers=concurrent_workers) as executor:
        futures = [
            executor.submit(make_request, query, i+1) 
            for i, query in enumerate(TEST_QUERIES)
        ]
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            
            status_icon = "✓" if result["status"] == "success" else "✗"
            print(f"{status_icon} Request {result['request_num']}: {', '.join(result['names'])} "
                  f"- {result['duration']:.2f}s ({result.get('status_code', 'N/A')})")
    
    total_time = time.time() - start_time
    
    # Calculate statistics
    successful = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] != "success"]
    
    if successful:
        durations = [r["duration"] for r in successful]
        avg_duration = sum(durations) / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)
    else:
        avg_duration = min_duration = max_duration = 0
    
    # Get final cache stats
    try:
        final_stats = requests.get(CACHE_STATS_URL).json()
    except:
        final_stats = {}
    
    # Print summary
    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"Total requests:    {len(results)}")
    print(f"Successful:        {len(successful)}")
    print(f"Failed:            {len(failed)}")
    print(f"Total time:        {total_time:.2f}s")
    print(f"Requests/sec:      {len(results)/total_time:.2f}")
    print(f"\nResponse times:")
    print(f"  Average:         {avg_duration:.2f}s")
    print(f"  Min:             {min_duration:.2f}s")
    print(f"  Max:             {max_duration:.2f}s")
    
    if final_stats:
        print(f"\nCache Statistics:")
        print(f"  Cache hits:      {final_stats.get('cache_hits', 0)}")
        print(f"  Cache misses:    {final_stats.get('cache_misses', 0)}")
        print(f"  Hit rate:        {final_stats.get('hit_rate_percent', 0):.1f}%")
        print(f"  Active entries:  {final_stats.get('active_entries', 0)}")
    
    print(f"{'='*60}\n")
    
    if failed:
        print("FAILED REQUESTS:")
        for r in failed:
            print(f"  - {r['names']}: {r.get('error', 'Unknown error')[:100]}")

if __name__ == "__main__":
    run_load_test(concurrent_workers=3)
