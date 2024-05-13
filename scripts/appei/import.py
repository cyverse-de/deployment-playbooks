#!/bin/env python

import argparse
import json
import requests
import pathlib
import os.path


def list_tools(server: str, access_token: str) -> dict:
    listing_url = "https://{}/terrain/admin/tools".format(server)
    res = requests.get(
        listing_url, headers={"Authorization": "Bearer {}".format(access_token)}
    )
    res.raise_for_status()
    return res.json()["tools"]


def list_apps(server: str, access_token: str, name: str) -> dict:
    listing_url = "https://{}/terrain/admin/apps".format(server)
    res = requests.get(
        listing_url,
        headers={"Authorization": "Bearer {}".format(access_token)},
        params={"search": name},
    )
    res.raise_for_status()
    return res.json()["apps"]


def is_in_listing(item: dict, listing: list[dict]) -> bool:
    for listed in listing:
        if listed["name"] == item["name"] and listed["version"] == item["version"]:
            return True
    return False


def clean_tool_for_import(tool: dict):
    if "permission" in tool:
        del tool["permission"]

    if "is_public" in tool:
        del tool["is_public"]

    if "container" in tool:
        if "interactive_apps" in tool["container"]:
            if "id" in tool["container"]["interactive_apps"]:
                del tool["container"]["interactive_apps"]["id"]

        if "image" in tool["container"]:
            if "id" in tool["container"]["image"]:
                del tool["container"]["image"]["id"]

        if "container_ports" in tool["container"]:
            for p in tool["container"]["container_ports"]:
                if "id" in p:
                    del p["id"]


def import_tool(import_url: str, access_token: str, tool: dict) -> dict:
    payload = json.dumps({"tools": [tool]})

    # Do the import
    res = requests.post(
        import_url,
        headers={
            "Authorization": "Bearer {}".format(access_token),
            "Content-Type": "application/json",
        },
        data=payload,
    )

    if not res.ok:
        print(res.text)
        res.raise_for_status()

    return res.json()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import app/tool definitions into a DE instance"
    )
    parser.add_argument(
        "--server",
        action="store",
        required=True,
        dest="server",
        help="The server to import apps into",
    )
    parser.add_argument(
        "-i",
        "--input",
        action="store",
        required=True,
        dest="input",
        help="The file containing the JSON defining an app and its tools",
    )
    args = parser.parse_args()

    # Read the access_token from the config directory.
    token_filepath = pathlib.Path(
        os.path.expanduser("~/.config/cyverse/discoenv/appei/{}".format(args.server))
    )

    token_data = None
    with open(token_filepath, "r") as token_file:
        token_data = json.load(token_file)

    if token_data is None:
        print("No token data was found, please run login.py")
        exit(1)

    print("Importing app and tools into server {}".format(args.server))

    # Read the import data from the input file.
    import_data = None
    with open(args.input, "r") as infile:
        import_data = json.load(infile)

    if import_data is None:
        print("No import data read from {}".format(args.input))
        exit(1)

    # Get a listing of the tools already in the DE.
    tool_listing = list_tools(args.server, token_data["access_token"])
    app_listing = list_apps(
        args.server, token_data["access_token"], import_data["name"]
    )

    # First, import the tools and get the IDs for them.
    tool_import_url = "https://{}/terrain/admin/tools".format(args.server)
    for t in import_data["tools"]:
        # Don't bother re-importing a tool if it's already in the DE.
        if is_in_listing(t, tool_listing):
            print("Skipping import of {} {}".format(t["name"], t["version"]))
            continue

        print("Importing tool {} {}...".format(t["name"], t["version"]))

        clean_tool_for_import(t)
        tool_res_data = import_tool(tool_import_url, token_data["access_token"], t)
        tool_id = tool_res_data["tool_ids"][0]

        print("Imported tool {} {} as ID {}".format(t["name"], t["version"], tool_id))

        t["id"] = tool_id

    app_import_url = "https://{}/terrain/apps/{}".format(
        args.server, import_data["system_id"]
    )

    if not is_in_listing(import_data, app_listing):
        print("Importing app {} {}".format(import_data["name"], import_data["version"]))
        import_url = "https://{}/terrain/apps/{}".format(import_data["system_id"])
        import_res = requests.post(
            import_url,
            headers={"Authorization": "Bearer {}".format(token_data["access_token"])},
            data=import_data,
        )
        import_res.raise_for_status()
        print(
            "Done importing app {} {}".format(
                import_data["name"], import_data["version"]
            )
        )
    else:
        print(
            "Skipping import of {} {}".format(
                import_data["name"], import_data["version"]
            )
        )
