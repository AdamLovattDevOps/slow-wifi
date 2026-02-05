#!/usr/bin/env python3
"""
Network Latency Analysis - Scientific Visualization
Hand-drawn style charts showing AWDL's impact on latency
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Enable XKCD sketch style
plt.xkcd()

# Human factors reference data (milliseconds)
HUMAN_FACTORS = {
    "Blink of an eye": 150,
    "Human reaction time (visual)": 250,
    "Perceivable delay threshold": 100,
    "\"Instant\" feel threshold": 50,
    "Pro gamer reaction": 150,
    "RDP responsive threshold": 20,
}

def load_report(filepath):
    """Load the optimizer report JSON."""
    with open(filepath) as f:
        return json.load(f)

def create_comparison_bar_chart(report, ax):
    """Bar chart comparing all settings."""
    tests = report["tests"]

    names = [t["setting_name"] for t in tests]
    # Shorten names for display
    short_names = ["Baseline\n(AWDL on)", "TCP Delayed\nACK off", "AWDL\noff", "Bluetooth\noff", "All\nOptimized"]

    avg_latency = [t["avg_latency_ms"] for t in tests]
    max_latency = [t["max_latency_ms"] for t in tests]
    spike_pct = [t["spike_percentage"] for t in tests]

    x = np.arange(len(names))
    width = 0.35

    bars1 = ax.bar(x - width/2, avg_latency, width, label='Avg Latency', color='#3498db', alpha=0.8)
    bars2 = ax.bar(x + width/2, max_latency, width, label='Max Latency', color='#e74c3c', alpha=0.8)

    # Add horizontal lines for human perception thresholds
    ax.axhline(y=50, color='green', linestyle='--', alpha=0.7, linewidth=2)
    ax.text(4.6, 55, '"Instant" feel\nthreshold (50ms)', fontsize=8, color='green', ha='right')

    ax.axhline(y=100, color='orange', linestyle='--', alpha=0.7, linewidth=2)
    ax.text(4.6, 105, 'Perceivable\ndelay (100ms)', fontsize=8, color='orange', ha='right')

    ax.set_ylabel('Latency (ms)')
    ax.set_title('The AWDL Horror Show\n(Lower is Better)', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(short_names, fontsize=9)
    ax.legend(loc='upper right')
    ax.set_ylim(0, 400)

    # Annotate the winner
    ax.annotate('THE\nFIX!', xy=(2, avg_latency[2]), xytext=(2, 80),
                fontsize=12, ha='center', color='green', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='green', lw=2))

def create_spike_comparison(report, ax):
    """Pie/donut showing spike percentages."""
    tests = report["tests"]

    settings = ["Baseline\n(AWDL on)", "AWDL off"]
    baseline_spikes = tests[0]["spike_percentage"]
    awdl_off_spikes = tests[2]["spike_percentage"]

    # Side by side comparison
    data_baseline = [baseline_spikes, 100 - baseline_spikes]
    data_fixed = [awdl_off_spikes, 100 - awdl_off_spikes]

    colors_bad = ['#e74c3c', '#2ecc71']
    colors_good = ['#e74c3c', '#2ecc71']

    # Two pie charts side by side
    ax.pie([29, 71], labels=['Spikes\n29%', 'OK\n71%'], colors=colors_bad,
           autopct='', startangle=90, center=(-1.5, 0), radius=1,
           wedgeprops=dict(width=0.5, edgecolor='white'))

    ax.pie([0.1, 99.9], labels=['Spikes\n0%', 'OK\n100%'], colors=['#ecf0f1', '#2ecc71'],
           autopct='', startangle=90, center=(1.5, 0), radius=1,
           wedgeprops=dict(width=0.5, edgecolor='white'))

    ax.text(-1.5, -1.6, 'BEFORE\n(AWDL on)', ha='center', fontsize=11, fontweight='bold', color='#e74c3c')
    ax.text(1.5, -1.6, 'AFTER\n(AWDL off)', ha='center', fontsize=11, fontweight='bold', color='#2ecc71')

    ax.set_title('Packets Over 15ms Threshold\n(Spike = Lag You Can Feel)', fontsize=12, fontweight='bold')
    ax.set_xlim(-3, 3)
    ax.set_ylim(-2.2, 1.5)
    ax.set_aspect('equal')
    ax.axis('off')

def create_timeline_comparison(report, ax):
    """Show raw RTT values over time for baseline vs AWDL off."""
    tests = report["raw_data"]

    baseline_rtts = tests[0]["raw_rtts"][:100]  # First 100 for clarity
    awdl_off_rtts = tests[2]["raw_rtts"][:100]

    x = range(len(baseline_rtts))

    ax.fill_between(x, baseline_rtts, alpha=0.3, color='#e74c3c', label='AWDL ON (Baseline)')
    ax.plot(x, baseline_rtts, color='#e74c3c', alpha=0.7, linewidth=1)

    ax.fill_between(x, awdl_off_rtts, alpha=0.5, color='#2ecc71', label='AWDL OFF')
    ax.plot(x, awdl_off_rtts, color='#2ecc71', alpha=0.9, linewidth=1.5)

    # Add RDP threshold line
    ax.axhline(y=20, color='blue', linestyle=':', alpha=0.8, linewidth=2)
    ax.text(102, 22, 'RDP "smooth"\nthreshold', fontsize=8, color='blue')

    ax.set_xlabel('Ping Sequence')
    ax.set_ylabel('Round Trip Time (ms)')
    ax.set_title('The Nightmare vs The Dream\n(First 100 Pings)', fontsize=12, fontweight='bold')
    ax.legend(loc='upper right')
    ax.set_ylim(0, 120)
    ax.set_xlim(0, 105)

def create_jitter_comparison(report, ax):
    """Box plot style comparison of jitter."""
    tests = report["raw_data"]

    # Calculate jitter for each test
    def calc_jitter(rtts):
        return [abs(rtts[i] - rtts[i-1]) for i in range(1, len(rtts))]

    baseline_jitter = calc_jitter(tests[0]["raw_rtts"])
    awdl_off_jitter = calc_jitter(tests[2]["raw_rtts"])

    data = [baseline_jitter, awdl_off_jitter]

    bp = ax.boxplot(data, labels=['AWDL ON\n(Baseline)', 'AWDL OFF'], patch_artist=True,
                    widths=0.6)

    colors = ['#e74c3c', '#2ecc71']
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)

    ax.set_ylabel('Jitter (ms)')
    ax.set_title('Jitter Distribution\n(Consistency of Connection)', fontsize=12, fontweight='bold')

    # Add annotation
    ax.annotate(f'Median: {np.median(baseline_jitter):.1f}ms',
                xy=(1, np.median(baseline_jitter)), xytext=(1.3, np.median(baseline_jitter) + 20),
                fontsize=9, color='#e74c3c')
    ax.annotate(f'Median: {np.median(awdl_off_jitter):.1f}ms',
                xy=(2, np.median(awdl_off_jitter)), xytext=(2.2, np.median(awdl_off_jitter) + 10),
                fontsize=9, color='#2ecc71')

def create_human_context_chart(report, ax):
    """Show latency in context of human perception."""

    # Data points
    categories = [
        ('Your LAN\n(AWDL off)', 4.3, '#2ecc71'),
        ('Your LAN\n(AWDL on)', 25.4, '#e74c3c'),
        ('Your spikes\n(AWDL on)', 93, '#c0392b'),
        ('RDP smooth\nthreshold', 20, '#3498db'),
        ('"Instant" feel\nthreshold', 50, '#9b59b6'),
        ('Perceivable\ndelay', 100, '#f39c12'),
        ('Human visual\nreaction', 250, '#7f8c8d'),
    ]

    categories = sorted(categories, key=lambda x: x[1])

    names = [c[0] for c in categories]
    values = [c[1] for c in categories]
    colors = [c[2] for c in categories]

    bars = ax.barh(names, values, color=colors, alpha=0.8, edgecolor='black', linewidth=1)

    # Add value labels
    for bar, val in zip(bars, values):
        ax.text(val + 5, bar.get_y() + bar.get_height()/2, f'{val:.0f}ms',
                va='center', fontsize=10, fontweight='bold')

    ax.set_xlabel('Latency (milliseconds)')
    ax.set_title('Putting It In Perspective\n(Human Perception Context)', fontsize=12, fontweight='bold')
    ax.set_xlim(0, 300)

    # Add a vertical line at the "instant" threshold
    ax.axvline(x=50, color='purple', linestyle='--', alpha=0.5)

def create_verdict_text(report, ax):
    """Create a text summary panel."""
    ax.axis('off')

    baseline = report["tests"][0]
    awdl_off = report["tests"][2]

    verdict = f"""
    THE VERDICT
    {'='*40}

    AWDL (AirDrop Wireless Direct Link) was
    hijacking your Wi-Fi radio every ~1.5 seconds
    to scan for nearby Apple devices.

    BEFORE (AWDL on):
      - Average latency: {baseline['avg_latency_ms']}ms
      - Maximum spike: {baseline['max_latency_ms']}ms
      - Packets with lag: {baseline['spike_percentage']}%
      - Jitter: {baseline['avg_jitter_ms']}ms

    AFTER (AWDL off):
      - Average latency: {awdl_off['avg_latency_ms']}ms
      - Maximum spike: {awdl_off['max_latency_ms']}ms
      - Packets with lag: {awdl_off['spike_percentage']}%
      - Jitter: {awdl_off['avg_jitter_ms']}ms

    IMPROVEMENT:
      - {baseline['avg_latency_ms'] / awdl_off['avg_latency_ms']:.1f}x faster average
      - {baseline['max_latency_ms'] / awdl_off['max_latency_ms']:.1f}x lower max spike
      - {baseline['avg_jitter_ms'] / awdl_off['avg_jitter_ms']:.1f}x more consistent

    For RDP: You went from "floaty mouse"
    to "basically local" responsiveness.
    """

    ax.text(0.05, 0.95, verdict, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='#ecf0f1', alpha=0.8))

def main():
    # Find the most recent report
    reports = list(Path('.').glob('optimizer_report_*.json'))
    if not reports:
        print("No optimizer report found!")
        return

    report_path = sorted(reports)[-1]  # Most recent
    print(f"Loading: {report_path}")
    report = load_report(report_path)

    # Create the figure with subplots
    fig = plt.figure(figsize=(16, 20))
    fig.suptitle('AWDL: The Silent Latency Killer\nA Scientific Analysis of Your Network Woes',
                 fontsize=18, fontweight='bold', y=0.98)

    # Create grid of subplots
    gs = fig.add_gridspec(4, 2, hspace=0.4, wspace=0.3,
                          left=0.08, right=0.95, top=0.92, bottom=0.05)

    # Row 1: Main comparison bar chart (spans both columns)
    ax1 = fig.add_subplot(gs[0, :])
    create_comparison_bar_chart(report, ax1)

    # Row 2: Timeline and spike comparison
    ax2 = fig.add_subplot(gs[1, 0])
    create_timeline_comparison(report, ax2)

    ax3 = fig.add_subplot(gs[1, 1])
    create_spike_comparison(report, ax3)

    # Row 3: Jitter and human context
    ax4 = fig.add_subplot(gs[2, 0])
    create_jitter_comparison(report, ax4)

    ax5 = fig.add_subplot(gs[2, 1])
    create_human_context_chart(report, ax5)

    # Row 4: Verdict text (spans both columns)
    ax6 = fig.add_subplot(gs[3, :])
    create_verdict_text(report, ax6)

    # Save the figure
    output_file = 'latency_analysis.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"\nSaved: {output_file}")

    # Also save a PDF for printing
    plt.savefig('latency_analysis.pdf', bbox_inches='tight', facecolor='white')
    print(f"Saved: latency_analysis.pdf")

    plt.show()

if __name__ == "__main__":
    main()
