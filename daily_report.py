#!/usr/bin/env python3
"""photomon-1 GCP 인프라 일일 모니터링 리포트 생성기"""

import os
import sys
import json
import datetime
import subprocess
import urllib.request
import ssl
from pathlib import Path

from google.oauth2 import service_account
from google.cloud import monitoring_v3, compute_v1

# ─── 설정 ───────────────────────────────────────────────
PROJECT_ID = "photomon-1"
KEY_FILE = "/Users/user/.config/gcloud/claude-code-sa-key.json"
OBSIDIAN_PATH = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Obsidian/Infra"
GITHUB_REPO = "siniabi/infra-monitoring"
REPO_LOCAL = Path.home() / "COMPANY/Dev/Infra/monitoring/infra-monitoring"

VMS = [
    {"name": "bizprint1", "zone": "asia-northeast3-b", "domain": "https://biz.photomon.com"},
    {"name": "photomon-sqlserver-vm", "zone": "asia-northeast3-b", "domain": None},
    {"name": "photomon-tplv", "zone": "asia-northeast3-b", "domain": "https://tplv.photomon.com"},
    {"name": "photomon-tpls2b", "zone": "asia-northeast3-b", "domain": "https://tpls.photomon.com"},
    {"name": "prepress-1", "zone": "asia-northeast3-b", "domain": None},
]

DISK_THRESHOLD = 80

# ─── 인증 ───────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/monitoring.read",
    "https://www.googleapis.com/auth/compute.readonly",
]

credentials = service_account.Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)


# ─── 유틸 ───────────────────────────────────────────────
def now_kst():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))


def check_http(url, timeout=10):
    """도메인 HTTP 상태 코드 확인"""
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return f"ERR: {type(e).__name__}"


# ─── VM 상태 수집 ────────────────────────────────────────
def get_vm_status():
    """Compute Engine API로 VM 상태 조회"""
    client = compute_v1.InstancesClient(credentials=credentials)
    results = []
    for vm in VMS:
        try:
            instance = client.get(project=PROJECT_ID, zone=vm["zone"], instance=vm["name"])
            results.append({
                "name": vm["name"],
                "status": instance.status,
                "machine_type": instance.machine_type.split("/")[-1],
                "zone": vm["zone"],
            })
        except Exception as e:
            results.append({
                "name": vm["name"],
                "status": f"ERROR: {e}",
                "machine_type": "N/A",
                "zone": vm["zone"],
            })
    return results


# ─── Cloud Monitoring 메트릭 수집 ─────────────────────────
def get_metrics():
    """CPU, 메모리, 디스크 메트릭 수집 (최근 1시간 평균)"""
    client = monitoring_v3.MetricServiceClient(credentials=credentials)
    project_name = f"projects/{PROJECT_ID}"

    end_time = datetime.datetime.now(datetime.timezone.utc)
    start_time = end_time - datetime.timedelta(hours=1)

    interval = monitoring_v3.TimeInterval(
        start_time=start_time,
        end_time=end_time,
    )

    metrics_config = [
        {
            "key": "cpu",
            "filter": f'metric.type = "compute.googleapis.com/instance/cpu/utilization" AND resource.labels.project_id = "{PROJECT_ID}"',
            "unit": "%",
            "multiplier": 100,
        },
        {
            "key": "disk_used_pct",
            "filter": f'metric.type = "agent.googleapis.com/disk/percent_used" AND resource.labels.project_id = "{PROJECT_ID}" AND metric.labels.state = "used"',
            "unit": "%",
            "multiplier": 1,
        },
        {
            "key": "memory_used_pct",
            "filter": f'metric.type = "agent.googleapis.com/memory/percent_used" AND resource.labels.project_id = "{PROJECT_ID}" AND metric.labels.state = "used"',
            "unit": "%",
            "multiplier": 1,
        },
    ]

    all_metrics = {}

    for mc in metrics_config:
        try:
            results = client.list_time_series(
                request={
                    "name": project_name,
                    "filter": mc["filter"],
                    "interval": interval,
                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                    "aggregation": monitoring_v3.Aggregation(
                        alignment_period={"seconds": 3600},
                        per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
                    ),
                }
            )
            for ts in results:
                instance_name = ts.resource.labels.get("instance_id", "unknown")
                # metric labels에서 device 정보 추출 (디스크용)
                device = ts.metric.labels.get("device", "")
                if instance_name not in all_metrics:
                    all_metrics[instance_name] = {"instance_id": instance_name}
                for point in ts.points:
                    val = point.value.double_value * mc["multiplier"]
                    if mc["key"] == "disk_used_pct":
                        # /dev/loop* 는 snap 읽기전용 마운트 → 항상 100%, 무시
                        if device.startswith("/dev/loop"):
                            continue
                        if "disks" not in all_metrics[instance_name]:
                            all_metrics[instance_name]["disks"] = {}
                        all_metrics[instance_name]["disks"][device] = round(val, 1)
                    else:
                        all_metrics[instance_name][mc["key"]] = round(val, 1)
        except Exception as e:
            print(f"[WARN] 메트릭 수집 실패 ({mc['key']}): {e}")

    return all_metrics


# ─── HTTP 헬스체크 ────────────────────────────────────────
def check_all_http():
    results = []
    for vm in VMS:
        if vm["domain"]:
            status = check_http(vm["domain"])
            results.append({
                "name": vm["name"],
                "domain": vm["domain"],
                "http_status": status,
            })
    return results


# ─── 알림 판별 ────────────────────────────────────────────
def check_alerts(vm_status, metrics, http_results):
    alerts = []

    for vm in vm_status:
        if vm["status"] not in ("RUNNING", "STAGING"):
            alerts.append(f"🔴 VM {vm['name']}: 상태 {vm['status']}")

    for instance_id, m in metrics.items():
        cpu = m.get("cpu")
        if cpu is not None and cpu > 90:
            alerts.append(f"🟡 CPU 높음: instance {instance_id} → {cpu}%")
        mem = m.get("memory_used_pct")
        if mem is not None and mem > 90:
            alerts.append(f"🟡 메모리 높음: instance {instance_id} → {mem}%")
        for device, pct in m.get("disks", {}).items():
            if pct > DISK_THRESHOLD:
                alerts.append(f"🔴 디스크 사용량 초과: instance {instance_id} [{device}] → {pct}%")

    for h in http_results:
        if isinstance(h["http_status"], int) and h["http_status"] < 400:
            continue
        alerts.append(f"🔴 HTTP 이상: {h['name']} ({h['domain']}) → {h['http_status']}")

    return alerts


# ─── 마크다운 리포트 생성 ─────────────────────────────────
def generate_report(vm_status, metrics, http_results, alerts):
    ts = now_kst()
    date_str = ts.strftime("%Y-%m-%d")
    time_str = ts.strftime("%H:%M KST")

    lines = [
        f"# 일일 인프라 리포트 — {date_str}",
        f"> 생성: {time_str}  |  프로젝트: `{PROJECT_ID}`",
        "",
    ]

    # 알림 섹션
    if alerts:
        lines.append("## ⚠️ 알림")
        for a in alerts:
            lines.append(f"- {a}")
        lines.append("")
    else:
        lines.append("## ✅ 알림 없음")
        lines.append("")

    # VM 상태
    lines.append("## VM 상태")
    lines.append("| VM | 상태 | 머신타입 | Zone |")
    lines.append("|---|---|---|---|")
    for vm in vm_status:
        status_icon = "🟢" if vm["status"] == "RUNNING" else "🔴"
        lines.append(f"| {vm['name']} | {status_icon} {vm['status']} | {vm['machine_type']} | {vm['zone']} |")
    lines.append("")

    # 메트릭
    lines.append("## 리소스 사용량 (최근 1시간 평균)")
    lines.append("| Instance ID | CPU (%) | Memory (%) |")
    lines.append("|---|---|---|")
    for iid, m in metrics.items():
        cpu = m.get("cpu", "N/A")
        mem = m.get("memory_used_pct", "N/A")
        lines.append(f"| {iid} | {cpu} | {mem} |")
    lines.append("")

    # 디스크
    has_disk = any("disks" in m for m in metrics.values())
    if has_disk:
        lines.append("### 디스크 사용량")
        lines.append("| Instance ID | Device | 사용률 (%) |")
        lines.append("|---|---|---|")
        for iid, m in metrics.items():
            for device, pct in m.get("disks", {}).items():
                warn = " ⚠️" if pct > DISK_THRESHOLD else ""
                lines.append(f"| {iid} | {device} | {pct}{warn} |")
        lines.append("")

    # HTTP 헬스체크
    lines.append("## HTTP 헬스체크")
    lines.append("| VM | 도메인 | 상태 |")
    lines.append("|---|---|---|")
    for h in http_results:
        ok = isinstance(h["http_status"], int) and h["http_status"] < 400
        icon = "🟢" if ok else "🔴"
        lines.append(f"| {h['name']} | {h['domain']} | {icon} {h['http_status']} |")
    lines.append("")

    lines.append("---")
    lines.append(f"_자동 생성 by `daily_report.py` | {ts.isoformat()}_")

    return "\n".join(lines)


# ─── 저장 & 푸시 ──────────────────────────────────────────
def save_obsidian(report, date_str):
    """Obsidian 볼트에 리포트 저장"""
    reports_dir = OBSIDIAN_PATH / "Reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    filepath = reports_dir / f"{date_str}-daily.md"
    filepath.write_text(report, encoding="utf-8")
    print(f"[OK] Obsidian 저장: {filepath}")
    return filepath


def push_github(report, date_str):
    """GitHub repo에 리포트 푸시"""
    repo_dir = REPO_LOCAL
    if not repo_dir.exists():
        print(f"[WARN] 로컬 repo 없음: {repo_dir}, git clone 시도")
        subprocess.run(
            ["gh", "repo", "clone", GITHUB_REPO, str(repo_dir)],
            check=True,
            capture_output=True,
        )

    reports_dir = repo_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    filepath = reports_dir / f"{date_str}-daily.md"
    filepath.write_text(report, encoding="utf-8")

    subprocess.run(["git", "-C", str(repo_dir), "add", "."], check=True, capture_output=True)

    result = subprocess.run(
        ["git", "-C", str(repo_dir), "diff", "--cached", "--quiet"],
        capture_output=True,
    )
    if result.returncode == 0:
        print("[INFO] 변경 사항 없음, push 스킵")
        return

    subprocess.run(
        ["git", "-C", str(repo_dir), "commit", "-m", f"report: {date_str} daily"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_dir), "push"],
        check=True,
        capture_output=True,
    )
    print(f"[OK] GitHub push 완료: {filepath}")


# ─── 메인 ────────────────────────────────────────────────
def main():
    test_mode = "--test" in sys.argv
    ts = now_kst()
    date_str = ts.strftime("%Y-%m-%d")

    print(f"=== 일일 인프라 리포트 생성 시작 ({date_str}) ===")

    print("[1/4] VM 상태 수집...")
    vm_status = get_vm_status()

    print("[2/4] Cloud Monitoring 메트릭 수집...")
    metrics = get_metrics()

    print("[3/4] HTTP 헬스체크...")
    http_results = check_all_http()

    print("[4/4] 알림 판별 & 리포트 생성...")
    alerts = check_alerts(vm_status, metrics, http_results)
    report = generate_report(vm_status, metrics, http_results, alerts)

    if test_mode:
        print("\n--- TEST MODE: 리포트 미리보기 ---")
        print(report)
        print("--- TEST MODE 끝 ---\n")
    else:
        save_obsidian(report, date_str)
        push_github(report, date_str)

    if alerts:
        print(f"\n⚠️ 알림 {len(alerts)}건:")
        for a in alerts:
            print(f"  {a}")
    else:
        print("\n✅ 이상 없음")

    print("=== 완료 ===")


if __name__ == "__main__":
    main()
