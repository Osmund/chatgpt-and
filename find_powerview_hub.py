#!/usr/bin/env python3
"""
Finn PowerView Hub på nettverket
"""

import requests
import socket
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
import time


class PowerViewListener(ServiceListener):
    def __init__(self):
        self.found = []
    
    def add_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name)
        if info:
            self.found.append(info)
            print(f"✅ Fant PowerView: {name}")
            print(f"   IP: {socket.inet_ntoa(info.addresses[0])}")
            print(f"   Port: {info.port}")


def scan_for_hub():
    """Scan for PowerView Hub via mDNS/Zeroconf"""
    print("🔍 Scanning for PowerView Hub...")
    
    zeroconf = Zeroconf()
    listener = PowerViewListener()
    
    # PowerView Gen 3 uses _PowerView-G3._tcp.local.
    browser = ServiceBrowser(zeroconf, "_PowerView-G3._tcp.local.", listener)
    
    print("   Waiting 10 seconds...")
    time.sleep(10)
    
    zeroconf.close()
    
    return listener.found


def test_hub(ip):
    """Test connection to PowerView Hub"""
    print(f"\n🧪 Testing connection to {ip}...")
    
    try:
        # PowerView Gen 3 API endpoint
        response = requests.get(f"http://{ip}/api/userdata", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ PowerView Hub found!")
            print(f"   Serial: {data.get('serialNumber', 'N/A')}")
            print(f"   Firmware: {data.get('firmware', {}).get('mainProcessor', {}).get('name', 'N/A')}")
            return True
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return False


def scan_network_for_hub():
    """Scan local network for PowerView Hub (fallback method)"""
    print("\n🔍 Scanning local network...")
    
    # Get local IP range
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"   Local IP: {local_ip}")
    
    # Extract network prefix (e.g., 192.168.1.x)
    ip_parts = local_ip.split('.')
    network_prefix = '.'.join(ip_parts[:3])
    
    print(f"   Scanning {network_prefix}.1-254...")
    
    for i in range(1, 255):
        ip = f"{network_prefix}.{i}"
        try:
            response = requests.get(f"http://{ip}/api/userdata", timeout=0.5)
            if response.status_code == 200:
                print(f"\n✅ Found PowerView Hub at {ip}!")
                data = response.json()
                print(f"   Serial: {data.get('serialNumber', 'N/A')}")
                return ip
        except:
            pass
    
    return None


if __name__ == "__main__":
    print("=" * 60)
    print("🦆 PowerView Hub Discovery")
    print("=" * 60)
    
    # Method 1: mDNS/Zeroconf
    found = scan_for_hub()
    
    if found:
        for info in found:
            ip = socket.inet_ntoa(info.addresses[0])
            test_hub(ip)
    else:
        print("\n⚠️  No hub found via mDNS, trying network scan...")
        ip = scan_network_for_hub()
        if ip:
            test_hub(ip)
        else:
            print("\n❌ Could not find PowerView Hub")
            print("   Make sure the hub is powered on and connected to the network")
