# AWDL Latency Diagnostic Tools

Scripts to diagnose and fix Wi-Fi latency issues on macOS caused by AWDL (AirDrop Wireless Direct Link).

## Scripts

- **jitter-check.py** - Continuous LAN latency monitor with spike detection
- **network_optimizer_test.py** - A/B tests various macOS network settings to find the culprit
- **visualize_results.py** - Generates charts from test results

## Quick Fix

```bash
# Disable AWDL immediately
sudo ifconfig awdl0 down

# Disable AirDrop permanently
defaults write com.apple.NetworkBrowser DisableAirDrop -bool YES

# Disable Handoff
defaults write com.apple.coreservices.useractivityd ActivityAdvertisingAllowed -bool NO
defaults write com.apple.coreservices.useractivityd ActivityReceivingAllowed -bool NO
```

Also disable in **System Settings → General → AirDrop & Handoff**.

See the [full blog post](https://adamlovattdevops.github.io/awdl-latency-killer/) for analysis and details.

## Disclaimer

These scripts modify system network settings. Use at your own risk. No warranty. Not responsible for any damage or issues.

## License

MIT
