from fastapi import FastAPI, HTTPException, Form, Query
from typing import Optional
from nornir import InitNornir
from nornir.core.filter import F
from nornir_napalm.plugins.tasks import napalm_get
from nornir_netmiko.tasks import netmiko_send_config, netmiko_send_command
from io import StringIO
from fastapi import Query 
import re
#os.chdir('/home/dansong/fastapi/inventory')
#os.chdir('/home/dansong/fastapi')


app = FastAPI()
#nr = InitNornir(config_file="config.yaml")
nr = InitNornir(config_file="config1.yaml")


def expand_interface(interface: str) -> str:
    # Optional logic to expand shorthand interfaces (e.g., Gi1/0/1 → GigabitEthernet1/0/1)
    return interface


@app.get("/get-config")
def get_config(hostname: str = Query(..., description="Hostname of the device")):
    """
    GET endpoint to retrieve the running configuration of a network device.
    """
    try:
        config_output = fetch_config(hostname)
        return {"hostname": hostname, "config": config_output}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


def fetch_config(hostname: str) -> str:
    """
    Get the running config of a specified host and return as string.
    """
    filtered_nr = nr.filter(hostname=hostname)
    if not filtered_nr.inventory.hosts:
        raise ValueError(f"Host '{hostname}' not found in inventory")

    result = filtered_nr.run(task=napalm_get, getters=["config"])

    output = StringIO()
    for host, task_result in result.items():
        output.write(f"\n{'=' * 50}\n")
        output.write(f"Configuration for {host}\n")
        output.write(f"{'=' * 50}\n")

        if task_result.failed:
            output.write(f"Failed to get config from {host}: {task_result.exception}\n")
            continue

        running_config = task_result.result["config"]["running"]
        config_lines = running_config.splitlines()

        output.write(f"Running Configuration ({len(config_lines)} lines):\n")
        output.write("-" * 30 + "\n")
        for line in config_lines:
            output.write(line + "\n")

    return output.getvalue()


@app.post("/change-vlan")
def change_vlan(
    host: str = Form(...),
    interface: str = Form(...),
    new_vlan: str = Form(...),
    description: Optional[str] = Form(None)
):
    """
    POST endpoint to change the VLAN of a specific interface on a switch.
    """
    if not all([host, interface, new_vlan]):
        raise HTTPException(status_code=400, detail="Missing required VLAN change data.")

    target = nr.filter(F(name=host))
    if not target.inventory.hosts:
        raise HTTPException(status_code=404, detail=f"Host '{host}' not found in inventory.")

    intf_full = expand_interface(interface)
    cmds = [
        f"interface {intf_full}",
        f"switchport access vlan {new_vlan}"
    ]
    if description:
        cmds.append(f"description {description}")
    cmds.append("exit")

    result = target.run(task=netmiko_send_config, config_commands=cmds)
    task = list(result.values())[0]

    if task.failed:
        raise HTTPException(status_code=500, detail=f"Failed to change VLAN: {task.result}")

    return {
        "message": f"Successfully changed {intf_full} to VLAN {new_vlan} on {host}",
        "host": host,
        "interface": intf_full,
        "vlan": new_vlan,
        "description": description
    }


@app.get("/port-status")
def port_status(
    host: str = Query(..., description="Hostname of the device"),
    interface: str = Query(..., description="Interface to check (e.g., Gi1/0/1)")
):
    """
    GET endpoint to check the status of a specific interface.
    Returns: host, interface, vlan, mac address, description, and port status (up/down).
    """
    try:
        status = fetch_port_status(host, interface)
        return status
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    

def expand_interface(interface: str) -> str:
    """
    Expands Cisco short interface names to full names.
    Examples:
      Gi1/0/48 -> GigabitEthernet1/0/48
      Fa0/1    -> FastEthernet0/1
      Te1/1/1  -> TenGigabitEthernet1/1/1
      Eth3     -> Ethernet3
    """
    interface = interface.strip()
    # Map short forms to full names
    mapping = {
        'gi': 'GigabitEthernet',
        'fa': 'FastEthernet',
        'te': 'TenGigabitEthernet',
        'fo': 'FortyGigabitEthernet',
        'hu': 'HundredGigabitEthernet',
        'eth': 'Ethernet',
        'lo': 'Loopback',
        'po': 'Port-channel',
        'vl': 'Vlan',
        'se': 'Serial',
        'tu': 'Tunnel',
    }
    # Match the short form at the start, case-insensitive
    match = re.match(r'^([a-zA-Z]+)([\d\/\.]+)$', interface)
    if match:
        prefix, rest = match.groups()
        prefix = prefix.lower()
        if prefix in mapping:
            return f"{mapping[prefix]}{rest}"
    # If no match, return as-is
    return interface   

@app.get("/port-status")
def port_status(
    host: str = Query(..., description="Hostname or IP of the device"),
    interface: str = Query(..., description="Interface to check (e.g., Gi1/0/48)")
):
    """
    GET endpoint to check the status of a specific interface.
    Returns: host, interface, vlan, mac address, description, and port status (up/down).
    """
    try:
        status = fetch_port_status(host, interface)
        return status
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

def fetch_port_status(hostname: str, interface: str):
    filtered_nr = nr.filter(F(name=hostname) | F(hostname=hostname))
    if not filtered_nr.inventory.hosts:
        raise ValueError(f"Host '{hostname}' not found in inventory")

    result = filtered_nr.run(
        task=napalm_get,
        getters=["interfaces", "mac_address_table", "vlans"]
    )
    task_result = list(result.values())[0]
    if task_result.failed:
        raise Exception(f"Failed to get interface details: {task_result.exception}")

    interfaces = task_result.result.get("interfaces", {})
    mac_table = task_result.result.get("mac_address_table", [])
    vlans = task_result.result.get("vlans", {})

    intf_full = expand_interface(interface)
    intf_info = interfaces.get(intf_full)
    if intf_info is None:
        raise ValueError(f"Interface '{intf_full}' not found on host '{hostname}'")

    intf_descr = intf_info.get("description", "")
    is_up = intf_info.get("is_up", False)
    status = "up" if is_up else "down"
    mac_address = intf_info.get("mac_address", "")

    # Try MAC address table first
    vlan = None
    for entry in mac_table:
        if entry.get("interface") == intf_full:
            vlan = entry.get("vlan")
            break

    # If not found, try to infer from vlans getter
    if vlan is None:
        for vlan_id, vlan_info in vlans.items():
            if 'interfaces' in vlan_info and intf_full in vlan_info['interfaces']:
                vlan = vlan_id
                break

    return {
        "host": hostname,
        "interface": intf_full,
        "vlan": vlan,
        "mac_address": mac_address,
        "description": intf_descr,
        "status": status
    }

@app.get("/find-mac")
def find_mac(mac: str = Query(..., description="MAC address in xxxx.yyyy.zzzz format")):
    found = []
    result = nr.run(
        task=netmiko_send_command,
        command_string=f"show mac address-table address {mac}",
        use_textfsm=True
    )
    for host, task_result in result.items():
        entries = task_result.result
        # If entries is a string, parsing failed or no result
        if not entries or isinstance(entries, str):
            continue
        for entry in entries:
            # Defensive: entry should be a dict, skip otherwise
            if not isinstance(entry, dict):
                continue
            interface = entry.get("destination_port")
            interfaces = interface if isinstance(interface, list) else [interface]
            skip = False
            for intf in interfaces:
                if not intf:
                    skip = True
                    break
                if intf.lower().startswith("po") or intf.lower().startswith("port-channel"):
                    skip = True
                    break
            if skip:
                continue
            for intf in interfaces:
                intf_result = nr.filter(name=host).run(
                    task=netmiko_send_command,
                    command_string=f"show interfaces {intf} switchport",
                    use_textfsm=True
                )
                switchport_info = intf_result[host][0].result
                if isinstance(switchport_info, list) and switchport_info:
                    switchport_info = switchport_info[0]
                mode = switchport_info.get("switchport_mode", "").lower()
                if "trunk" in mode:
                    skip = True
                    break
            if skip:
                continue
            for intf in interfaces:
                found.append({
                    "switch": host,
                    "interface": intf,
                    "vlan": entry.get("vlan"),
                    "mac_type": entry.get("type"),
                })
    if not found:
        raise HTTPException(status_code=404, detail="MAC address not found on any access port.")
    return {
        "host": host,
        "interface": intf
    }


#uvicorn main:app --reload
# lsof -i :8000
# 300a.60a0.324b