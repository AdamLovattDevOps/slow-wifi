#!/usr/bin/env python3
"""
Network Latency Optimizer - Diagnostic Test Suite
Tests various macOS network settings to identify what's causing latency spikes.
Idempotent: saves and restores all original settings.
"""

import subprocess
import time
import re
import os
import sys
import json
import datetime
import statistics
from dataclasses import dataclass, asdict
from typing import Optional, Callable

# --- CONFIGURATION ---
TARGET = "192.168.0.243"
PINGS_PER_TEST = 200
PING_INTERVAL = 0.2
SPIKE_THRESHOLD = 15.0
# ---------------------

@dataclass
class TestResult:
    setting_name: str
    setting_value: str
    packets_sent: int
    packets_lost: int
    avg_latency_ms: float
    max_latency_ms: float
    min_latency_ms: float
    avg_jitter_ms: float
    spike_count: int
    spike_percentage: float
    raw_rtts: list

@dataclass
class SettingState:
    name: str
    get_cmd: list
    enable_cmd: list
    disable_cmd: list
    parse_current: Callable
    requires_sudo: bool = True
    original_value: Optional[str] = None

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def log(msg, color=None):
    if color:
        print(f"{color}{msg}{Colors.RESET}")
    else:
        print(msg)

def run_cmd(cmd, check=False):
    """Run a command and return output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.stdout.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", 1
    except Exception as e:
        return str(e), 1

def check_sudo():
    """Verify we have sudo access."""
    result, code = run_cmd(["sudo", "-n", "true"])
    if code != 0:
        log("This script requires sudo privileges.", Colors.RED)
        log("Please run: sudo -v", Colors.YELLOW)
        log("Then run this script again.", Colors.YELLOW)
        sys.exit(1)

def parse_sysctl(output):
    """Parse sysctl output like 'net.inet.tcp.delayed_ack: 3'"""
    if ':' in output:
        return output.split(':')[-1].strip()
    return output.strip()

def parse_awdl(output):
    """Parse AWDL state - returns 'on' or 'off'"""
    # ifconfig output contains 'status: active' or similar
    if 'status: active' in output.lower():
        return 'on'
    return 'off'

def parse_bluetooth(output):
    """Parse Bluetooth power state."""
    if '1' in output or 'on' in output.lower():
        return 'on'
    return 'off'

def get_awdl_state():
    """Get AWDL interface state."""
    output, _ = run_cmd(["ifconfig", "awdl0"])
    return parse_awdl(output)

def get_bluetooth_state():
    """Get Bluetooth state using blueutil if available, otherwise system_profiler."""
    # Try blueutil first (faster)
    output, code = run_cmd(["blueutil", "--power"])
    if code == 0:
        return 'on' if output.strip() == '1' else 'off'

    # Fallback to system_profiler
    output, _ = run_cmd(["system_profiler", "SPBluetoothDataType"])
    if 'State: On' in output:
        return 'on'
    return 'off'

# Define testable settings
SETTINGS = [
    SettingState(
        name="TCP Delayed ACK",
        get_cmd=["sysctl", "net.inet.tcp.delayed_ack"],
        enable_cmd=["sudo", "sysctl", "-w", "net.inet.tcp.delayed_ack=3"],  # default/enabled
        disable_cmd=["sudo", "sysctl", "-w", "net.inet.tcp.delayed_ack=0"],  # disabled = lower latency
        parse_current=parse_sysctl,
    ),
    SettingState(
        name="TCP Send/Recv Autotuning",
        get_cmd=["sysctl", "net.inet.tcp.doautorcvbuf"],
        enable_cmd=["sudo", "sysctl", "-w", "net.inet.tcp.doautorcvbuf=1"],
        disable_cmd=["sudo", "sysctl", "-w", "net.inet.tcp.doautorcvbuf=0"],
        parse_current=parse_sysctl,
    ),
]

class NetworkOptimizer:
    def __init__(self):
        self.results: list[TestResult] = []
        self.original_states: dict[str, str] = {}
        self.report_file = f"optimizer_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self.has_blueutil = self._check_blueutil()

    def _check_blueutil(self):
        """Check if blueutil is installed for Bluetooth control."""
        _, code = run_cmd(["which", "blueutil"])
        return code == 0

    def save_original_states(self):
        """Save current state of all settings."""
        log("\n📋 Saving original settings...", Colors.CYAN)

        for setting in SETTINGS:
            output, _ = run_cmd(setting.get_cmd)
            setting.original_value = setting.parse_current(output)
            self.original_states[setting.name] = setting.original_value
            log(f"  {setting.name}: {setting.original_value}")

        # AWDL state
        self.original_states["AWDL"] = get_awdl_state()
        log(f"  AWDL: {self.original_states['AWDL']}")

        # Bluetooth state
        self.original_states["Bluetooth"] = get_bluetooth_state()
        log(f"  Bluetooth: {self.original_states['Bluetooth']}")

    def restore_original_states(self):
        """Restore all settings to original values."""
        log("\n🔄 Restoring original settings...", Colors.CYAN)

        for setting in SETTINGS:
            if setting.original_value is not None:
                if setting.name == "TCP Delayed ACK":
                    cmd = ["sudo", "sysctl", "-w", f"net.inet.tcp.delayed_ack={setting.original_value}"]
                elif setting.name == "TCP Send/Recv Autotuning":
                    cmd = ["sudo", "sysctl", "-w", f"net.inet.tcp.doautorcvbuf={setting.original_value}"]
                else:
                    continue
                run_cmd(cmd)
                log(f"  Restored {setting.name} to {setting.original_value}")

        # Restore AWDL
        if self.original_states.get("AWDL") == "on":
            run_cmd(["sudo", "ifconfig", "awdl0", "up"])
        log(f"  Restored AWDL to {self.original_states.get('AWDL', 'unknown')}")

        # Restore Bluetooth
        if self.has_blueutil:
            bt_val = "1" if self.original_states.get("Bluetooth") == "on" else "0"
            run_cmd(["blueutil", "--power", bt_val])
            log(f"  Restored Bluetooth to {self.original_states.get('Bluetooth', 'unknown')}")

    def run_ping_test(self, label: str, setting_value: str) -> TestResult:
        """Run a ping test and collect statistics."""
        log(f"\n🔬 Testing: {label} = {setting_value}", Colors.BOLD)
        log(f"   Sending {PINGS_PER_TEST} pings to {TARGET}...")

        rtts = []
        lost = 0

        for i in range(PINGS_PER_TEST):
            cmd = ["ping", "-c", "1", "-W", "1000", TARGET]
            result = subprocess.run(cmd, capture_output=True, text=True)

            match = re.search(r'time=([\d.]+)', result.stdout)
            if match:
                rtts.append(float(match.group(1)))
            else:
                lost += 1

            # Progress indicator every 50 pings
            if (i + 1) % 50 == 0:
                log(f"   Progress: {i + 1}/{PINGS_PER_TEST}", Colors.CYAN)

            time.sleep(PING_INTERVAL)

        # Calculate statistics
        if rtts:
            jitter_values = [abs(rtts[i] - rtts[i-1]) for i in range(1, len(rtts))]
            spike_count = sum(1 for r in rtts if r > SPIKE_THRESHOLD)

            result = TestResult(
                setting_name=label,
                setting_value=setting_value,
                packets_sent=PINGS_PER_TEST,
                packets_lost=lost,
                avg_latency_ms=round(statistics.mean(rtts), 2),
                max_latency_ms=round(max(rtts), 2),
                min_latency_ms=round(min(rtts), 2),
                avg_jitter_ms=round(statistics.mean(jitter_values), 2) if jitter_values else 0,
                spike_count=spike_count,
                spike_percentage=round((spike_count / len(rtts)) * 100, 1),
                raw_rtts=rtts
            )
        else:
            result = TestResult(
                setting_name=label,
                setting_value=setting_value,
                packets_sent=PINGS_PER_TEST,
                packets_lost=lost,
                avg_latency_ms=0,
                max_latency_ms=0,
                min_latency_ms=0,
                avg_jitter_ms=0,
                spike_count=0,
                spike_percentage=0,
                raw_rtts=[]
            )

        # Print summary
        color = Colors.GREEN if result.spike_percentage < 10 else (Colors.YELLOW if result.spike_percentage < 25 else Colors.RED)
        log(f"   Result: avg={result.avg_latency_ms}ms, max={result.max_latency_ms}ms, jitter={result.avg_jitter_ms}ms, spikes={result.spike_percentage}%", color)

        return result

    def apply_setting(self, name: str, enable: bool):
        """Apply a specific setting."""
        if name == "TCP Delayed ACK":
            val = "3" if enable else "0"
            run_cmd(["sudo", "sysctl", "-w", f"net.inet.tcp.delayed_ack={val}"])
        elif name == "TCP Send/Recv Autotuning":
            val = "1" if enable else "0"
            run_cmd(["sudo", "sysctl", "-w", f"net.inet.tcp.doautorcvbuf={val}"])
        elif name == "AWDL":
            if enable:
                run_cmd(["sudo", "ifconfig", "awdl0", "up"])
            else:
                run_cmd(["sudo", "ifconfig", "awdl0", "down"])
        elif name == "Bluetooth":
            if self.has_blueutil:
                run_cmd(["blueutil", "--power", "1" if enable else "0"])
                time.sleep(2)  # Bluetooth needs time to toggle

    def run_all_tests(self):
        """Run the complete test suite."""
        log("=" * 60, Colors.BOLD)
        log("  NETWORK LATENCY OPTIMIZER - DIAGNOSTIC TEST", Colors.BOLD)
        log("=" * 60, Colors.BOLD)
        log(f"Target: {TARGET}")
        log(f"Pings per test: {PINGS_PER_TEST}")
        log(f"Spike threshold: {SPIKE_THRESHOLD}ms")

        # Save original states first
        self.save_original_states()

        try:
            # Test 1: Baseline (current settings)
            log("\n" + "=" * 60)
            log("TEST 1: BASELINE (current settings)", Colors.BOLD)
            log("=" * 60)
            self.results.append(self.run_ping_test("Baseline", "current"))

            # Test 2: TCP Delayed ACK disabled
            log("\n" + "=" * 60)
            log("TEST 2: TCP DELAYED ACK DISABLED", Colors.BOLD)
            log("=" * 60)
            self.apply_setting("TCP Delayed ACK", enable=False)
            self.results.append(self.run_ping_test("TCP Delayed ACK", "disabled"))
            self.apply_setting("TCP Delayed ACK", enable=True)  # Reset

            # Test 3: AWDL disabled
            log("\n" + "=" * 60)
            log("TEST 3: AWDL (AirDrop) DISABLED", Colors.BOLD)
            log("=" * 60)
            self.apply_setting("AWDL", enable=False)
            time.sleep(1)  # Let interface settle
            self.results.append(self.run_ping_test("AWDL", "disabled"))
            self.apply_setting("AWDL", enable=True)  # Reset

            # Test 4: Bluetooth disabled (if blueutil available)
            if self.has_blueutil:
                log("\n" + "=" * 60)
                log("TEST 4: BLUETOOTH DISABLED", Colors.BOLD)
                log("=" * 60)
                self.apply_setting("Bluetooth", enable=False)
                self.results.append(self.run_ping_test("Bluetooth", "disabled"))
                self.apply_setting("Bluetooth", enable=True)  # Reset
            else:
                log("\n⚠️  Skipping Bluetooth test (install blueutil: brew install blueutil)", Colors.YELLOW)

            # Test 5: All optimizations combined
            log("\n" + "=" * 60)
            log("TEST 5: ALL OPTIMIZATIONS COMBINED", Colors.BOLD)
            log("=" * 60)
            self.apply_setting("TCP Delayed ACK", enable=False)
            self.apply_setting("AWDL", enable=False)
            if self.has_blueutil:
                self.apply_setting("Bluetooth", enable=False)
            time.sleep(1)
            self.results.append(self.run_ping_test("All Optimizations", "enabled"))

        finally:
            # Always restore original settings
            self.restore_original_states()

        # Generate report
        self.generate_report()

    def generate_report(self):
        """Generate JSON report for analysis."""
        log("\n" + "=" * 60, Colors.BOLD)
        log("  GENERATING REPORT", Colors.BOLD)
        log("=" * 60, Colors.BOLD)

        # Prepare report data
        report = {
            "test_date": datetime.datetime.now().isoformat(),
            "target": TARGET,
            "pings_per_test": PINGS_PER_TEST,
            "spike_threshold_ms": SPIKE_THRESHOLD,
            "original_settings": self.original_states,
            "tests": [],
            "recommendations": []
        }

        # Add test results (without raw_rtts for readability, stored separately)
        for result in self.results:
            test_data = asdict(result)
            test_data["raw_rtts"] = f"[{len(result.raw_rtts)} values]"  # Summarize
            report["tests"].append(test_data)

        # Find best performing configuration
        valid_results = [r for r in self.results if r.avg_latency_ms > 0]
        if valid_results:
            best_by_latency = min(valid_results, key=lambda r: r.avg_latency_ms)
            best_by_spikes = min(valid_results, key=lambda r: r.spike_percentage)
            best_by_jitter = min(valid_results, key=lambda r: r.avg_jitter_ms)

            baseline = self.results[0] if self.results else None

            report["analysis"] = {
                "best_avg_latency": {"setting": best_by_latency.setting_name, "value": best_by_latency.avg_latency_ms},
                "best_spike_rate": {"setting": best_by_spikes.setting_name, "value": best_by_spikes.spike_percentage},
                "best_jitter": {"setting": best_by_jitter.setting_name, "value": best_by_jitter.avg_jitter_ms},
            }

            # Generate recommendations
            if baseline:
                for result in self.results[1:]:
                    improvement = baseline.spike_percentage - result.spike_percentage
                    if improvement > 5:
                        report["recommendations"].append({
                            "setting": result.setting_name,
                            "action": f"Set to {result.setting_value}",
                            "spike_reduction": f"{improvement:.1f}%",
                            "jitter_change": f"{baseline.avg_jitter_ms - result.avg_jitter_ms:.2f}ms"
                        })

        # Save full report with raw data
        full_report = report.copy()
        full_report["raw_data"] = [asdict(r) for r in self.results]

        with open(self.report_file, 'w') as f:
            json.dump(full_report, f, indent=2)

        log(f"\n📄 Report saved to: {Colors.BOLD}{self.report_file}{Colors.RESET}")

        # Print summary table
        log("\n" + "=" * 60)
        log("  RESULTS SUMMARY", Colors.BOLD)
        log("=" * 60)
        log(f"{'Setting':<25} {'Avg(ms)':<10} {'Max(ms)':<10} {'Jitter':<10} {'Spikes':<10}")
        log("-" * 65)

        for result in self.results:
            color = Colors.GREEN if result.spike_percentage < 10 else (Colors.YELLOW if result.spike_percentage < 25 else Colors.RED)
            log(f"{result.setting_name:<25} {result.avg_latency_ms:<10} {result.max_latency_ms:<10} {result.avg_jitter_ms:<10} {result.spike_percentage:<10}%", color)

        # Print recommendations
        if report.get("recommendations"):
            log("\n" + "=" * 60)
            log("  RECOMMENDATIONS", Colors.BOLD)
            log("=" * 60)
            for rec in report["recommendations"]:
                log(f"✅ {rec['setting']}: {rec['action']} (reduces spikes by {rec['spike_reduction']})", Colors.GREEN)
        else:
            log("\n⚠️  No significant improvements found from software settings.", Colors.YELLOW)
            log("   The issue may be hardware or router-related.", Colors.YELLOW)

def main():
    log("\n🔍 Network Latency Optimizer - Diagnostic Mode", Colors.BOLD)
    log("   This will test various macOS network settings")
    log("   and measure their impact on latency.\n")

    # Check for sudo
    check_sudo()

    # Run tests
    optimizer = NetworkOptimizer()

    try:
        optimizer.run_all_tests()
    except KeyboardInterrupt:
        log("\n\n⚠️  Test interrupted!", Colors.YELLOW)
        log("   Restoring original settings...", Colors.YELLOW)
        optimizer.restore_original_states()
        log("   Settings restored. Partial results may be available.", Colors.GREEN)
        sys.exit(1)

if __name__ == "__main__":
    main()
