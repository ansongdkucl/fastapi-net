from fastapi import FastAPI, HTTPException, Form
from pydantic import BaseModel
from typing import Optional
from nornir import InitNornir
from nornir.core.filter import F
from nornir_netmiko.tasks import netmiko_send_config

app = FastAPI()
nr = InitNornir(config_file="config.yaml")


def expand_interface(interface: str) -> str:
    # Add your actual interface expansion logic here
    return interface  # Placeholder – adjust as needed


@app.post("/change-vlan")
def change_vlan(
    host: str = Form(...),
    interface: str = Form(...),
    new_vlan: str = Form(...),
    description: Optional[str] = Form(None)
):
    # Validate all required fields are present
    if not all([host, interface, new_vlan]):
        raise HTTPException(status_code=400, detail="Missing required VLAN change data.")

    # Build full interface string (e.g., GigabitEthernet0/1)
    intf_full = expand_interface(interface)

    # Prepare command list
    cmds = [
        f"interface {intf_full}",
        f"switchport access vlan {new_vlan}"
    ]
    if description:
        cmds.append(f"description {description}")
    cmds.append("exit")

    # Filter Nornir host
    target = nr.filter(F(name=host))
    if not target.inventory.hosts:
        raise HTTPException(status_code=404, detail=f"Host '{host}' not found in inventory.")

    # Run the command
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
