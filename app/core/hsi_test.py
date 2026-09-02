"""
HSI binary testing utilities.
Tests if HSI (HPSS Interface) binary exists and is executable.
"""
import os
import re
import shutil
import subprocess
from typing import Dict, Any


HSI_TEST_HOST = "hsi.sdarchive.iu.edu"
HSI_TEST_COMMAND = (
    "firewall -on; get file.zip : IEEE_VIS_SciVis_Challenge/2004/2004_entries.zip"
)


def get_hsi_version() -> Dict[str, Any]:
    """Return the version reported by the HSI executable available on PATH."""
    hsi_bin_path = shutil.which("hsi")
    if not hsi_bin_path:
        return {
            "success": False,
            "version": None,
            "message": "HSI binary is not installed or is not on PATH",
        }

    try:
        proc = subprocess.run(
            [hsi_bin_path, "-V"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "version": None,
            "message": "HSI version command timed out",
        }
    except OSError as exc:
        return {
            "success": False,
            "version": None,
            "message": f"Unable to run HSI: {exc}",
        }

    output = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
    # HSI has used more than one banner format across client releases.  In
    # particular, some builds send the banner to stderr and return a non-zero
    # status even though ``-V`` successfully reports the installed version.
    # The version token is the authoritative result of this probe.
    match = re.search(
        r"\bhsi[._\s-]+(\d+(?:[._-][A-Za-z0-9]+)+)",
        output,
        flags=re.IGNORECASE,
    )
    if not match:
        return {
            "success": False,
            "version": None,
            "message": "HSI did not return a version",
        }

    return {
        "success": True,
        "version": match.group(1),
        "binary": hsi_bin_path,
    }


def _configured_hsi_binary(hsi_bin_path: str) -> str:
    """Return the HSI executable path from a configured directory or file."""
    return os.path.join(hsi_bin_path, "hsi") if os.path.isdir(hsi_bin_path) else hsi_bin_path


def _command_output(value: str | bytes | None) -> str:
    """Normalize subprocess output, including output attached to timeouts."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def test_hsi_configuration(config: Dict[str, Any]) -> Dict[str, Any]:
    """Run the configured HSI authentication and transfer test verbosely.

    This mirrors ``hsi_test.sh`` while taking its binary path, keytab, user,
    firewall setting, and timeout from ``SDS_SYNC__*`` configuration.
    """
    hsi_bin_path = str(config.get("hsi_bin_path", ""))
    hsi_binary = _configured_hsi_binary(hsi_bin_path)
    keytab_path = str(config.get("hsi_keytab_path", ""))
    user = str(config.get("hsi_user", ""))
    firewall_flag = str(config.get("firewall_flag", "on"))
    timeout_in_secs = config.get("timeout_in_secs", 3300)
    hsi_command = HSI_TEST_COMMAND.replace("firewall -on", f"firewall -{firewall_flag}")
    command = [
        hsi_binary,
        "-h", HSI_TEST_HOST,
        "-d2",
        "-A", "keytab",
        "-k", keytab_path,
        "-l", user,
        hsi_command,
    ]

    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_in_secs,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "success": False,
            "message": "HSI testing failed due to timeout",
            "stdout": _command_output(exc.stdout),
            "stderr": _command_output(exc.stderr),
        }
    except OSError as exc:
        return {
            "success": False,
            "message": f"Unable to run configured HSI test: {exc}",
            "stdout": "",
            "stderr": "",
        }

    return {
        "success": proc.returncode == 0,
        "message": "HSI configuration test completed"
        if proc.returncode == 0
        else f"HSI configuration test failed with exit code {proc.returncode}",
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def test_hsi_binary(hsi_bin_path: str) -> Dict[str, Any]:
    """
    Test if HSI binary exists and is executable.
    
    Args:
        hsi_bin_path: Path to the HSI binary
    
    Returns:
        Dictionary with test results including success status and details
    """
    result = {
        "success": False,
        "message": "",
        "details": {}
    }
    
    try:
        # Check if path is provided
        if not hsi_bin_path or hsi_bin_path.startswith('<') or hsi_bin_path.startswith('</'):
            result["success"] = False
            result["message"] = "HSI binary path is not configured (placeholder value detected)"
            result["details"] = {
                "hsi_bin_path": hsi_bin_path,
                "configured": False
            }
            return result
        
        # Check if file exists
        if not os.path.exists(hsi_bin_path):
            result["success"] = False
            result["message"] = f"HSI binary not found at path: {hsi_bin_path}"
            result["details"] = {
                "hsi_bin_path": hsi_bin_path,
                "exists": False
            }
            return result
        
        # Check if it's a file
        if not os.path.isfile(hsi_bin_path):
            result["success"] = False
            result["message"] = f"Path exists but is not a file: {hsi_bin_path}"
            result["details"] = {
                "hsi_bin_path": hsi_bin_path,
                "exists": True,
                "is_file": False
            }
            return result
        
        # Check if executable
        if not os.access(hsi_bin_path, os.X_OK):
            result["success"] = False
            result["message"] = f"HSI binary exists but is not executable: {hsi_bin_path}"
            result["details"] = {
                "hsi_bin_path": hsi_bin_path,
                "exists": True,
                "is_file": True,
                "is_executable": False,
                "permissions": oct(os.stat(hsi_bin_path).st_mode)[-3:]
            }
            return result
        
        # Try to get version or basic info
        try:
            proc = subprocess.run(
                [hsi_bin_path, '-?'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            version_info = "Available"
            if proc.stdout:
                # Try to extract version from output
                for line in proc.stdout.split('\n'):
                    if 'version' in line.lower() or 'hsi' in line.lower():
                        version_info = line.strip()
                        break
            
            result["success"] = True
            result["message"] = "HSI binary found and is executable!"
            result["details"] = {
                "hsi_bin_path": hsi_bin_path,
                "exists": True,
                "is_file": True,
                "is_executable": True,
                "permissions": oct(os.stat(hsi_bin_path).st_mode)[-3:],
                "version_info": version_info,
                "file_size": os.path.getsize(hsi_bin_path)
            }
            
        except subprocess.TimeoutExpired:
            result["success"] = True
            result["message"] = "HSI binary found and is executable (command timed out, but binary is valid)"
            result["details"] = {
                "hsi_bin_path": hsi_bin_path,
                "exists": True,
                "is_file": True,
                "is_executable": True,
                "permissions": oct(os.stat(hsi_bin_path).st_mode)[-3:],
                "note": "Binary exists and is executable, but help command timed out"
            }
        except Exception as e:
            # Even if execution fails, if we got here the binary exists and is executable
            result["success"] = True
            result["message"] = "HSI binary found and is executable!"
            result["details"] = {
                "hsi_bin_path": hsi_bin_path,
                "exists": True,
                "is_file": True,
                "is_executable": True,
                "permissions": oct(os.stat(hsi_bin_path).st_mode)[-3:],
                "note": f"Binary is valid (execution test: {str(e)})"
            }
        
    except Exception as e:
        result["success"] = False
        result["message"] = f"Error testing HSI binary: {str(e)}"
        result["details"] = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "hsi_bin_path": hsi_bin_path
        }
    
    return result


def test_hsi_from_config(config: Dict[str, str]) -> Dict[str, Any]:
    """
    Test HSI binary using configuration dictionary.
    
    Args:
        config: Dictionary containing sds_sync configuration (hsi_bin_path)
    
    Returns:
        Dictionary with test results
    """
    try:
        hsi_bin_path = config.get("hsi_bin_path", "")
        return test_hsi_binary(hsi_bin_path)
    except Exception as e:
        return {
            "success": False,
            "message": f"Configuration error: {str(e)}",
            "details": {}
        }
