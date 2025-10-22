#!/usr/bin/env python3
"""
Quick diagnostic tool to test dashboard connectivity
"""
import requests
import time

PI_URL = "http://100.101.51.31:5000"
BACKEND_URL = "http://localhost:5001"

def test_pi_connection():
    """Test connection to Pi"""
    print("\n🔍 Testing Pi Connection...")
    endpoints = [
        "/api/fall_status",
        "/api/emergency_status", 
        "/api/environmental"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{PI_URL}{endpoint}", timeout=2)
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ {endpoint}: {data}")
            else:
                print(f"  ❌ {endpoint}: HTTP {response.status_code}")
        except Exception as e:
            print(f"  ❌ {endpoint}: {e}")

def test_backend_connection():
    """Test connection to backend"""
    print("\n🔍 Testing Backend Connection...")
    endpoints = [
        "/api/status",
        "/api/stats",
        "/api/fall_status",
        "/api/emergency_status",
        "/api/environmental"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{BACKEND_URL}{endpoint}", timeout=2)
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ {endpoint}: {data}")
            else:
                print(f"  ❌ {endpoint}: HTTP {response.status_code}")
        except Exception as e:
            print(f"  ❌ {endpoint}: {e}")

def test_video_stream():
    """Test video stream"""
    print("\n🔍 Testing Video Streams...")
    
    # Test Pi stream
    print("  Testing Pi MJPEG stream...")
    try:
        response = requests.get(f"{PI_URL}/video_feed", stream=True, timeout=5)
        if response.status_code == 200:
            # Read first chunk
            chunk = next(response.iter_content(1024))
            print(f"  ✅ Pi video stream working ({len(chunk)} bytes received)")
        else:
            print(f"  ❌ Pi video stream: HTTP {response.status_code}")
    except Exception as e:
        print(f"  ❌ Pi video stream: {e}")
    
    # Test backend stream
    print("  Testing Backend MJPEG stream...")
    try:
        response = requests.get(f"{BACKEND_URL}/api/video_feed", stream=True, timeout=5)
        if response.status_code == 200:
            chunk = next(response.iter_content(1024))
            print(f"  ✅ Backend video stream working ({len(chunk)} bytes received)")
        else:
            print(f"  ❌ Backend video stream: HTTP {response.status_code}")
    except Exception as e:
        print(f"  ❌ Backend video stream: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 Vision Assistant Diagnostic Tool")
    print("=" * 60)
    
    test_pi_connection()
    test_backend_connection()
    test_video_stream()
    
    print("\n" + "=" * 60)
    print("📋 Summary:")
    print("  If all tests pass ✅, dashboard should work")
    print("  If tests fail ❌:")
    print("    1. Make sure run.py is running")
    print("    2. Make sure Pi script (aa.py/abcd.py) is running")
    print("    3. Check firewall/network settings")
    print("=" * 60)

