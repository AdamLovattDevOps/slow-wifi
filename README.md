# AWDL Latency Diagnostic Tools

Scripts to diagnose and fix Wi-Fi latency issues on macOS caused by AWDL (AirDrop Wireless Direct Link).

## Scripts

- **jitter-check.py** - Continuous LAN latency monitor with spike detection
- **network_optimizer_test.py** - A/B tests various macOS network settings to find the culprit
- **visualize_results.py** - Generates charts from test results

## Quick Fix

If you just want to disable AWDL:

```bash
sudo ifconfig awdl0 down
```

See the [blog post](https://adamlovattdevops.github.io/awdl-latency-killer/) for permanent fix and full analysis.

## Disclaimer

These scripts modify system network settings. Use at your own risk. No warranty. Not responsible for any damage or issues.

## License

MIT
