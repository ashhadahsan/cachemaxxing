# Acme product reference

Specifications, settings paths and troubleshooting guides for every current Acme router and mesh node.

## Models

| Model | Radio | Ethernet ports | Max speed | Warranty |
|---|---|--:|---|---|
| AX1800 | dual-band | 4 | 1.8 Gbps | 2 years |
| AX3000 | dual-band | 4 | 3 Gbps | 2 years |
| AX5400 | tri-band | 6 | 5.4 Gbps | 2 years |
| AXE7800 | tri-band | 8 | 7.8 Gbps | 2 years |
| BE9300 | tri-band Wi-Fi 7 | 8 | 9.3 Gbps | 2 years |
| BE19000 Pro | quad-band Wi-Fi 7 | 12 | 19 Gbps | 3 years |
| Mesh M2 node | dual-band mesh | 2 | 1.2 Gbps | 2 years |
| Mesh M6 node | tri-band mesh | 4 | 5.4 Gbps | 2 years |

## Guest network

Where: Settings → Wi-Fi → Guest network.

What it does: isolates visitors from your devices; pick a separate name and an expiry time.

Support by model:

- AX1800: supported.
- AX3000: supported.
- AX5400: supported (app 4.2 or later).
- AXE7800: supported.
- BE9300: supported.
- BE19000 Pro: supported.
- Mesh M2 node: supported.
- Mesh M6 node: limited: no schedules.

## Parental controls

Where: Settings → Family → Profiles.

What it does: creates per-person schedules, content filters and pause buttons.

Support by model:

- AX1800: supported.
- AX3000: limited: no schedules.
- AX5400: supported on firmware 3.1+.
- AXE7800: supported.
- BE9300: supported.
- BE19000 Pro: supported.
- Mesh M2 node: supported.
- Mesh M6 node: supported.

## Port forwarding

Where: Settings → Advanced → Port forwarding.

What it does: maps an external port to a device; prefer UPnP off and explicit rules.

Support by model:

- AX1800: limited: no schedules.
- AX3000: limited: no schedules.
- AX5400: supported.
- AXE7800: limited: no schedules.
- BE9300: supported.
- BE19000 Pro: limited: no schedules.
- Mesh M2 node: supported on firmware 3.1+.
- Mesh M6 node: supported.

## VPN server

Where: Settings → Advanced → VPN.

What it does: supports WireGuard and OpenVPN; WireGuard is faster on every model.

Support by model:

- AX1800: supported on firmware 3.1+.
- AX3000: limited: no schedules.
- AX5400: supported (app 4.2 or later).
- AXE7800: supported.
- BE9300: supported.
- BE19000 Pro: supported on firmware 3.1+.
- Mesh M2 node: supported (app 4.2 or later).
- Mesh M6 node: supported (app 4.2 or later).

## QoS

Where: Settings → Advanced → Quality of service.

What it does: prioritises video calls and gaming; set your real upload and download speeds first.

Support by model:

- AX1800: supported.
- AX3000: supported.
- AX5400: supported (app 4.2 or later).
- AXE7800: supported.
- BE9300: supported.
- BE19000 Pro: supported on firmware 3.1+.
- Mesh M2 node: supported.
- Mesh M6 node: supported (app 4.2 or later).

## Band steering

Where: Settings → Wi-Fi → Smart connect.

What it does: moves devices to the best band automatically; turn it off for old smart-home plugs.

Support by model:

- AX1800: supported (app 4.2 or later).
- AX3000: limited: no schedules.
- AX5400: supported (app 4.2 or later).
- AXE7800: supported.
- BE9300: supported on firmware 3.1+.
- BE19000 Pro: limited: no schedules.
- Mesh M2 node: supported.
- Mesh M6 node: supported on firmware 3.1+.

## WPA3

Where: Settings → Wi-Fi → Security.

What it does: uses WPA3-Personal; switch to WPA2/WPA3 mixed mode for devices older than 2019.

Support by model:

- AX1800: supported.
- AX3000: limited: no schedules.
- AX5400: supported (app 4.2 or later).
- AXE7800: limited: no schedules.
- BE9300: supported (app 4.2 or later).
- BE19000 Pro: limited: no schedules.
- Mesh M2 node: supported.
- Mesh M6 node: supported.

## Firmware updates

Where: Settings → System → Firmware.

What it does: checks nightly; you can install manually and see release notes.

Support by model:

- AX1800: supported.
- AX3000: supported.
- AX5400: supported (app 4.2 or later).
- AXE7800: supported.
- BE9300: supported.
- BE19000 Pro: supported.
- Mesh M2 node: supported on firmware 3.1+.
- Mesh M6 node: supported (app 4.2 or later).

## Troubleshooting: Slow speeds

1. Run the speed test in the app next to the router.
2. Restart the router and the modem, modem first.
3. Move the router off the floor and away from metal and fish tanks.
4. Check QoS speeds match your plan.
5. Update firmware.

Model notes:

- AX1800: use the app wizard, not the web page.
- AX3000: hold Reset 15 seconds on this model.
- AX5400: check the rear status LED first.
- AXE7800: hold Reset 15 seconds on this model.
- BE9300: hold Reset 15 seconds on this model.
- BE19000 Pro: check the rear status LED first.
- Mesh M2 node: hold Reset 15 seconds on this model.
- Mesh M6 node: no special steps.

## Troubleshooting: Dropping connections

1. Check whether drops happen on one band or both.
2. Change the 2.4 GHz channel to 1, 6 or 11.
3. Disable band steering for affected devices.
4. Look for interference from microwaves or baby monitors.
5. Collect logs in the app and escalate if drops continue.

Model notes:

- AX1800: Ethernet backhaul recommended.
- AX3000: check the rear status LED first.
- AX5400: Ethernet backhaul recommended.
- AXE7800: check the rear status LED first.
- BE9300: check the rear status LED first.
- BE19000 Pro: use the app wizard, not the web page.
- Mesh M2 node: use the app wizard, not the web page.
- Mesh M6 node: hold Reset 15 seconds on this model.

## Troubleshooting: No internet light

1. Confirm the modem has internet with a laptop on its Ethernet port.
2. Reseat the WAN cable in the yellow port.
3. Power-cycle the modem for 60 seconds.
4. Set WAN type to automatic in the app.
5. Call the ISP if the modem itself is offline.

Model notes:

- AX1800: Ethernet backhaul recommended.
- AX3000: check the rear status LED first.
- AX5400: hold Reset 15 seconds on this model.
- AXE7800: no special steps.
- BE9300: check the rear status LED first.
- BE19000 Pro: no special steps.
- Mesh M2 node: hold Reset 15 seconds on this model.
- Mesh M6 node: use the app wizard, not the web page.

## Troubleshooting: Forgot Wi-Fi password

1. Open the Acme Home app → Wi-Fi → Show password.
2. If the app is not signed in, use the label under the router for the default.
3. If the password was changed and lost, factory-reset by holding Reset for 10 seconds.
4. Set up again in the app.
5. Change the password to something new and memorable.

Model notes:

- AX1800: hold Reset 15 seconds on this model.
- AX3000: no special steps.
- AX5400: check the rear status LED first.
- AXE7800: Ethernet backhaul recommended.
- BE9300: hold Reset 15 seconds on this model.
- BE19000 Pro: check the rear status LED first.
- Mesh M2 node: use the app wizard, not the web page.
- Mesh M6 node: use the app wizard, not the web page.

## Troubleshooting: Mesh node offline

1. Bring the node within two rooms of the router.
2. Check the node LED: blue is good, amber is weak, red is offline.
3. Restart the node.
4. Re-pair from the app → Mesh → Add node.
5. Use Ethernet backhaul if walls are thick.

Model notes:

- AX1800: use the app wizard, not the web page.
- AX3000: check the rear status LED first.
- AX5400: hold Reset 15 seconds on this model.
- AXE7800: check the rear status LED first.
- BE9300: check the rear status LED first.
- BE19000 Pro: Ethernet backhaul recommended.
- Mesh M2 node: Ethernet backhaul recommended.
- Mesh M6 node: hold Reset 15 seconds on this model.

## Troubleshooting: Overheating

1. Make sure vents are not covered.
2. Keep the router out of cabinets and direct sun.
3. Check the fan setting on Pro models.
4. Unplug immediately if there is smoke, swelling or a burning smell.
5. Escalate as a safety issue.

Model notes:

- AX1800: Ethernet backhaul recommended.
- AX3000: use the app wizard, not the web page.
- AX5400: Ethernet backhaul recommended.
- AXE7800: use the app wizard, not the web page.
- BE9300: hold Reset 15 seconds on this model.
- BE19000 Pro: check the rear status LED first.
- Mesh M2 node: check the rear status LED first.
- Mesh M6 node: Ethernet backhaul recommended.

## FAQ

- **Can the AX1800 use guest network?** Yes; open Settings → Wi-Fi → Guest network. On the AX1800 (dual-band, 4 ports) it isolates visitors from your devices; pick a separate name and an expiry time.
- **Can the AX1800 use parental controls?** Yes; open Settings → Family → Profiles. On the AX1800 (dual-band, 4 ports) it creates per-person schedules, content filters and pause buttons.
- **Can the AX1800 use port forwarding?** Yes; open Settings → Advanced → Port forwarding. On the AX1800 (dual-band, 4 ports) it maps an external port to a device; prefer UPnP off and explicit rules.
- **Can the AX1800 use vpn server?** Yes; open Settings → Advanced → VPN. On the AX1800 (dual-band, 4 ports) it supports WireGuard and OpenVPN; WireGuard is faster on every model.
- **Can the AX1800 use qos?** Yes; open Settings → Advanced → Quality of service. On the AX1800 (dual-band, 4 ports) it prioritises video calls and gaming; set your real upload and download speeds first.
- **Can the AX1800 use band steering?** Yes; open Settings → Wi-Fi → Smart connect. On the AX1800 (dual-band, 4 ports) it moves devices to the best band automatically; turn it off for old smart-home plugs.
- **Can the AX1800 use wpa3?** Yes; open Settings → Wi-Fi → Security. On the AX1800 (dual-band, 4 ports) it uses WPA3-Personal; switch to WPA2/WPA3 mixed mode for devices older than 2019.
- **Can the AX1800 use firmware updates?** Yes; open Settings → System → Firmware. On the AX1800 (dual-band, 4 ports) it checks nightly; you can install manually and see release notes.
- **Can the AX3000 use guest network?** Yes; open Settings → Wi-Fi → Guest network. On the AX3000 (dual-band, 4 ports) it isolates visitors from your devices; pick a separate name and an expiry time.
- **Can the AX3000 use parental controls?** Yes; open Settings → Family → Profiles. On the AX3000 (dual-band, 4 ports) it creates per-person schedules, content filters and pause buttons.
- **Can the AX3000 use port forwarding?** Yes; open Settings → Advanced → Port forwarding. On the AX3000 (dual-band, 4 ports) it maps an external port to a device; prefer UPnP off and explicit rules.
- **Can the AX3000 use vpn server?** Yes; open Settings → Advanced → VPN. On the AX3000 (dual-band, 4 ports) it supports WireGuard and OpenVPN; WireGuard is faster on every model.
- **Can the AX3000 use qos?** Yes; open Settings → Advanced → Quality of service. On the AX3000 (dual-band, 4 ports) it prioritises video calls and gaming; set your real upload and download speeds first.
- **Can the AX3000 use band steering?** Yes; open Settings → Wi-Fi → Smart connect. On the AX3000 (dual-band, 4 ports) it moves devices to the best band automatically; turn it off for old smart-home plugs.
- **Can the AX3000 use wpa3?** Yes; open Settings → Wi-Fi → Security. On the AX3000 (dual-band, 4 ports) it uses WPA3-Personal; switch to WPA2/WPA3 mixed mode for devices older than 2019.
- **Can the AX3000 use firmware updates?** Yes; open Settings → System → Firmware. On the AX3000 (dual-band, 4 ports) it checks nightly; you can install manually and see release notes.
- **Can the AX5400 use guest network?** Yes; open Settings → Wi-Fi → Guest network. On the AX5400 (tri-band, 6 ports) it isolates visitors from your devices; pick a separate name and an expiry time.
- **Can the AX5400 use parental controls?** Yes; open Settings → Family → Profiles. On the AX5400 (tri-band, 6 ports) it creates per-person schedules, content filters and pause buttons.
- **Can the AX5400 use port forwarding?** Yes; open Settings → Advanced → Port forwarding. On the AX5400 (tri-band, 6 ports) it maps an external port to a device; prefer UPnP off and explicit rules.
- **Can the AX5400 use vpn server?** Yes; open Settings → Advanced → VPN. On the AX5400 (tri-band, 6 ports) it supports WireGuard and OpenVPN; WireGuard is faster on every model.
- **Can the AX5400 use qos?** Yes; open Settings → Advanced → Quality of service. On the AX5400 (tri-band, 6 ports) it prioritises video calls and gaming; set your real upload and download speeds first.
- **Can the AX5400 use band steering?** Yes; open Settings → Wi-Fi → Smart connect. On the AX5400 (tri-band, 6 ports) it moves devices to the best band automatically; turn it off for old smart-home plugs.
- **Can the AX5400 use wpa3?** Yes; open Settings → Wi-Fi → Security. On the AX5400 (tri-band, 6 ports) it uses WPA3-Personal; switch to WPA2/WPA3 mixed mode for devices older than 2019.
- **Can the AX5400 use firmware updates?** Yes; open Settings → System → Firmware. On the AX5400 (tri-band, 6 ports) it checks nightly; you can install manually and see release notes.
- **Can the AXE7800 use guest network?** Yes; open Settings → Wi-Fi → Guest network. On the AXE7800 (tri-band, 8 ports) it isolates visitors from your devices; pick a separate name and an expiry time.
- **Can the AXE7800 use parental controls?** Yes; open Settings → Family → Profiles. On the AXE7800 (tri-band, 8 ports) it creates per-person schedules, content filters and pause buttons.
- **Can the AXE7800 use port forwarding?** Yes; open Settings → Advanced → Port forwarding. On the AXE7800 (tri-band, 8 ports) it maps an external port to a device; prefer UPnP off and explicit rules.
- **Can the AXE7800 use vpn server?** Yes; open Settings → Advanced → VPN. On the AXE7800 (tri-band, 8 ports) it supports WireGuard and OpenVPN; WireGuard is faster on every model.
- **Can the AXE7800 use qos?** Yes; open Settings → Advanced → Quality of service. On the AXE7800 (tri-band, 8 ports) it prioritises video calls and gaming; set your real upload and download speeds first.
- **Can the AXE7800 use band steering?** Yes; open Settings → Wi-Fi → Smart connect. On the AXE7800 (tri-band, 8 ports) it moves devices to the best band automatically; turn it off for old smart-home plugs.
- **Can the AXE7800 use wpa3?** Yes; open Settings → Wi-Fi → Security. On the AXE7800 (tri-band, 8 ports) it uses WPA3-Personal; switch to WPA2/WPA3 mixed mode for devices older than 2019.
- **Can the AXE7800 use firmware updates?** Yes; open Settings → System → Firmware. On the AXE7800 (tri-band, 8 ports) it checks nightly; you can install manually and see release notes.
- **Can the BE9300 use guest network?** Yes; open Settings → Wi-Fi → Guest network. On the BE9300 (tri-band Wi-Fi 7, 8 ports) it isolates visitors from your devices; pick a separate name and an expiry time.
- **Can the BE9300 use parental controls?** Yes; open Settings → Family → Profiles. On the BE9300 (tri-band Wi-Fi 7, 8 ports) it creates per-person schedules, content filters and pause buttons.
- **Can the BE9300 use port forwarding?** Yes; open Settings → Advanced → Port forwarding. On the BE9300 (tri-band Wi-Fi 7, 8 ports) it maps an external port to a device; prefer UPnP off and explicit rules.
- **Can the BE9300 use vpn server?** Yes; open Settings → Advanced → VPN. On the BE9300 (tri-band Wi-Fi 7, 8 ports) it supports WireGuard and OpenVPN; WireGuard is faster on every model.
- **Can the BE9300 use qos?** Yes; open Settings → Advanced → Quality of service. On the BE9300 (tri-band Wi-Fi 7, 8 ports) it prioritises video calls and gaming; set your real upload and download speeds first.
- **Can the BE9300 use band steering?** Yes; open Settings → Wi-Fi → Smart connect. On the BE9300 (tri-band Wi-Fi 7, 8 ports) it moves devices to the best band automatically; turn it off for old smart-home plugs.
- **Can the BE9300 use wpa3?** Yes; open Settings → Wi-Fi → Security. On the BE9300 (tri-band Wi-Fi 7, 8 ports) it uses WPA3-Personal; switch to WPA2/WPA3 mixed mode for devices older than 2019.
- **Can the BE9300 use firmware updates?** Yes; open Settings → System → Firmware. On the BE9300 (tri-band Wi-Fi 7, 8 ports) it checks nightly; you can install manually and see release notes.
- **Can the BE19000 Pro use guest network?** Yes; open Settings → Wi-Fi → Guest network. On the BE19000 Pro (quad-band Wi-Fi 7, 12 ports) it isolates visitors from your devices; pick a separate name and an expiry time.
- **Can the BE19000 Pro use parental controls?** Yes; open Settings → Family → Profiles. On the BE19000 Pro (quad-band Wi-Fi 7, 12 ports) it creates per-person schedules, content filters and pause buttons.
- **Can the BE19000 Pro use port forwarding?** Yes; open Settings → Advanced → Port forwarding. On the BE19000 Pro (quad-band Wi-Fi 7, 12 ports) it maps an external port to a device; prefer UPnP off and explicit rules.
- **Can the BE19000 Pro use vpn server?** Yes; open Settings → Advanced → VPN. On the BE19000 Pro (quad-band Wi-Fi 7, 12 ports) it supports WireGuard and OpenVPN; WireGuard is faster on every model.
- **Can the BE19000 Pro use qos?** Yes; open Settings → Advanced → Quality of service. On the BE19000 Pro (quad-band Wi-Fi 7, 12 ports) it prioritises video calls and gaming; set your real upload and download speeds first.
- **Can the BE19000 Pro use band steering?** Yes; open Settings → Wi-Fi → Smart connect. On the BE19000 Pro (quad-band Wi-Fi 7, 12 ports) it moves devices to the best band automatically; turn it off for old smart-home plugs.
- **Can the BE19000 Pro use wpa3?** Yes; open Settings → Wi-Fi → Security. On the BE19000 Pro (quad-band Wi-Fi 7, 12 ports) it uses WPA3-Personal; switch to WPA2/WPA3 mixed mode for devices older than 2019.
- **Can the BE19000 Pro use firmware updates?** Yes; open Settings → System → Firmware. On the BE19000 Pro (quad-band Wi-Fi 7, 12 ports) it checks nightly; you can install manually and see release notes.
- **Can the Mesh M2 node use guest network?** Yes; open Settings → Wi-Fi → Guest network. On the Mesh M2 node (dual-band mesh, 2 ports) it isolates visitors from your devices; pick a separate name and an expiry time.
- **Can the Mesh M2 node use parental controls?** Yes; open Settings → Family → Profiles. On the Mesh M2 node (dual-band mesh, 2 ports) it creates per-person schedules, content filters and pause buttons.
- **Can the Mesh M2 node use port forwarding?** Yes; open Settings → Advanced → Port forwarding. On the Mesh M2 node (dual-band mesh, 2 ports) it maps an external port to a device; prefer UPnP off and explicit rules.
- **Can the Mesh M2 node use vpn server?** Yes; open Settings → Advanced → VPN. On the Mesh M2 node (dual-band mesh, 2 ports) it supports WireGuard and OpenVPN; WireGuard is faster on every model.
- **Can the Mesh M2 node use qos?** Yes; open Settings → Advanced → Quality of service. On the Mesh M2 node (dual-band mesh, 2 ports) it prioritises video calls and gaming; set your real upload and download speeds first.
- **Can the Mesh M2 node use band steering?** Yes; open Settings → Wi-Fi → Smart connect. On the Mesh M2 node (dual-band mesh, 2 ports) it moves devices to the best band automatically; turn it off for old smart-home plugs.
- **Can the Mesh M2 node use wpa3?** Yes; open Settings → Wi-Fi → Security. On the Mesh M2 node (dual-band mesh, 2 ports) it uses WPA3-Personal; switch to WPA2/WPA3 mixed mode for devices older than 2019.
- **Can the Mesh M2 node use firmware updates?** Yes; open Settings → System → Firmware. On the Mesh M2 node (dual-band mesh, 2 ports) it checks nightly; you can install manually and see release notes.
- **Can the Mesh M6 node use guest network?** Yes; open Settings → Wi-Fi → Guest network. On the Mesh M6 node (tri-band mesh, 4 ports) it isolates visitors from your devices; pick a separate name and an expiry time.
- **Can the Mesh M6 node use parental controls?** Yes; open Settings → Family → Profiles. On the Mesh M6 node (tri-band mesh, 4 ports) it creates per-person schedules, content filters and pause buttons.
- **Can the Mesh M6 node use port forwarding?** Yes; open Settings → Advanced → Port forwarding. On the Mesh M6 node (tri-band mesh, 4 ports) it maps an external port to a device; prefer UPnP off and explicit rules.
- **Can the Mesh M6 node use vpn server?** Yes; open Settings → Advanced → VPN. On the Mesh M6 node (tri-band mesh, 4 ports) it supports WireGuard and OpenVPN; WireGuard is faster on every model.
- **Can the Mesh M6 node use qos?** Yes; open Settings → Advanced → Quality of service. On the Mesh M6 node (tri-band mesh, 4 ports) it prioritises video calls and gaming; set your real upload and download speeds first.
- **Can the Mesh M6 node use band steering?** Yes; open Settings → Wi-Fi → Smart connect. On the Mesh M6 node (tri-band mesh, 4 ports) it moves devices to the best band automatically; turn it off for old smart-home plugs.
- **Can the Mesh M6 node use wpa3?** Yes; open Settings → Wi-Fi → Security. On the Mesh M6 node (tri-band mesh, 4 ports) it uses WPA3-Personal; switch to WPA2/WPA3 mixed mode for devices older than 2019.
- **Can the Mesh M6 node use firmware updates?** Yes; open Settings → System → Firmware. On the Mesh M6 node (tri-band mesh, 4 ports) it checks nightly; you can install manually and see release notes.
