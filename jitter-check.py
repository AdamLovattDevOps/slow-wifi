import subprocess
import time
import re
import sys
import argparse
import statistics
import platform
import datetime
import json

# --- CONFIGURATION ---
INTERVAL = 0.2
SPIKE_THRESHOLD = 15.0
# ---------------------

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

class Logger:
    def __init__(self):
        self.filename = f"latency_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        self.file = open(self.filename, "w")
        print(f"Logging to file: {Colors.BOLD}{self.filename}{Colors.RESET}")
    
    def log(self, text, color=None, is_header=False):
        # Print to console with color
        if color:
            print(f"{color}{text}{Colors.RESET}")
        else:
            print(text)
        
        # Write to file (strip color codes for clean text)
        clean_text = text
        self.file.write(clean_text + "\n")
        self.file.flush()

    def close(self):
        self.file.close()

def get_ping_command(target):
    system = platform.system().lower()
    if "darwin" in system or "linux" in system:
        return ["ping", "-c", "1", "-W", "1000", target]
    else:
        return ["ping", "-n", "1", "-w", "1000", target]

def parse_time(output):
    match = re.search(r'time=([\d.]+)', str(output))
    if match: return float(match.group(1))
    return None

def analyze_lan(target):
    logger = Logger()

    # Header
    logger.log("--- LAN LATENCY DIAGNOSTIC REPORT ---")
    logger.log(f"Start Time: {datetime.datetime.now()}")
    logger.log(f"Target IP: {target}")
    logger.log(f"Ping Interval: {INTERVAL}s")
    logger.log(f"Spike Threshold: {SPIKE_THRESHOLD}ms")
    logger.log("-" * 60)
    logger.log(f"{'SEQ':<6} {'TIME':<26} {'RTT(ms)':<10} {'JITTER':<10} {'STATUS'}")
    logger.log("-" * 60)

    stats = {
        "sent": 0, "received": 0, "rtts": [], "jitter_values": [], 
        "spikes": 0, "high_jitter_events": 0
    }
    
    prev_rtt = None
    seq = 1

    try:
        while True:
            cmd = get_ping_command(target)
            # Run ping
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            timestamp = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
            
            stats["sent"] += 1
            rtt = parse_time(result.stdout)

            current_jitter = 0.0
            status_msg = "OK"
            row_color = Colors.GREEN

            if rtt is not None:
                stats["received"] += 1
                stats["rtts"].append(rtt)
                
                if prev_rtt is not None:
                    current_jitter = abs(rtt - prev_rtt)
                    stats["jitter_values"].append(current_jitter)

                # Analysis Logic
                if rtt > SPIKE_THRESHOLD:
                    row_color = Colors.RED
                    status_msg = "LAG SPIKE"
                    stats["spikes"] += 1
                elif current_jitter > 5.0:
                    row_color = Colors.YELLOW
                    status_msg = "HIGH JITTER"
                    stats["high_jitter_events"] += 1
                else:
                    row_color = Colors.GREEN
                    status_msg = "OK"

                log_line = f"{seq:<6} {timestamp:<26} {rtt:<10.2f} {current_jitter:<10.2f} {status_msg}"
                logger.log(log_line, row_color)
                prev_rtt = rtt
            else:
                row_color = Colors.RED
                log_line = f"{seq:<6} {timestamp:<26} {'TIMEOUT':<10} {'---':<10} PACKET LOSS"
                logger.log(log_line, row_color)
                prev_rtt = None

            seq += 1
            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        # --- SUMMARY GENERATION ---
        logger.log("\n" + "=" * 60)
        logger.log("TEST SUMMARY")
        logger.log("=" * 60)
        
        if stats["sent"] == 0:
            logger.close()
            return

        loss_pct = ((stats["sent"] - stats["received"]) / stats["sent"]) * 100
        avg_rtt = statistics.mean(stats["rtts"]) if stats["rtts"] else 0
        max_rtt = max(stats["rtts"]) if stats["rtts"] else 0
        avg_jitter = statistics.mean(stats["jitter_values"]) if stats["jitter_values"] else 0
        
        logger.log(f"Packets Sent:    {stats['sent']}")
        logger.log(f"Packets Lost:    {stats['sent'] - stats['received']} ({loss_pct:.2f}%)")
        logger.log(f"Avg Latency:     {avg_rtt:.2f} ms")
        logger.log(f"Max Latency:     {max_rtt:.2f} ms")
        logger.log(f"Avg Jitter:      {avg_jitter:.2f} ms")
        logger.log(f"Spike Events:    {stats['spikes']} (RTT > {SPIKE_THRESHOLD}ms)")
        
        # --- BOT-FRIENDLY JSON BLOCK ---
        logger.log("\n--- MACHINE READABLE SUMMARY (JSON) ---")
        json_summary = {
            "target": target,
            "duration_seconds": stats["sent"] * INTERVAL,
            "total_packets": stats["sent"],
            "packet_loss_pct": round(loss_pct, 2),
            "avg_latency_ms": round(avg_rtt, 2),
            "max_latency_ms": round(max_rtt, 2),
            "avg_jitter_ms": round(avg_jitter, 2),
            "stability_score": "POOR" if (loss_pct > 0 or avg_jitter > 5) else "GOOD",
            "diagnosis": []
        }
        
        if loss_pct > 0: json_summary["diagnosis"].append("Packet Loss detected (Wi-Fi interference or hardware fault)")
        if avg_jitter > 4: json_summary["diagnosis"].append("High Jitter (Mouse floatiness imminent)")
        if stats["spikes"] > (stats["sent"] * 0.05): json_summary["diagnosis"].append("Frequent Latency Spikes (Background process interruption)")
        
        logger.log(json.dumps(json_summary, indent=4))
        logger.close()
        print(f"\n{Colors.BOLD}Report saved to: {logger.filename}{Colors.RESET}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LAN latency diagnostic tool")
    parser.add_argument("target", help="Target IP address to ping (e.g., 192.168.1.1)")
    args = parser.parse_args()
    analyze_lan(args.target)