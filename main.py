from fastapi import FastAPI, HTTPException, Form, Query
from typing import Optional
from nornir import InitNornir
from nornir.core.filter import F
from nornir_napalm.plugins.tasks import napalm_get
from nornir_netmiko.tasks import netmiko_send_config
from io import StringIO

app = FastAPI()
nr = InitNornir(config_file="config.yaml")


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
