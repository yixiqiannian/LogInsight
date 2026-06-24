import json
import urllib.request
import time
from datetime import datetime, timedelta
import random

BASE = "http://localhost:8000"

def send_logs(logs):
    data = json.dumps({"logs": logs}).encode()
    req = urllib.request.Request(
        BASE + "/api/webhook/inbound",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def generate_k8s_logs():
    now = datetime.now()
    logs = []

    base_time = now - timedelta(minutes=30)

    scenarios = [
        {
            "service": "kubelet",
            "scenario": "pod-crashloop",
            "logs": [
                ("info", "Pod default/nginx-7c9b9d56f8-2xqzf started"),
                ("info", "Container nginx started"),
                ("warn", "Readiness probe failed: HTTP probe failed with statuscode: 500"),
                ("info", "Container nginx failed liveness probe, will be restarted"),
                ("error", "Back-off restarting failed container nginx in pod nginx-7c9b9d56f8-2xqzf_default"),
                ("warn", "Pod nginx-7c9b9d56f8-2xqzf is restarting again (restart count: 3)"),
                ("error", "Pod default/nginx-7c9b9d56f8-2xqzf status: CrashLoopBackOff"),
                ("warn", "Container nginx exit code: 1, reason: Error"),
                ("error", "CrashLoopBackOff: nginx pod restarted 5 times in the last 10 minutes"),
            ]
        },
        {
            "service": "kubelet",
            "scenario": "image-pull-fail",
            "logs": [
                ("info", "Pulling image \"myapp:v2.0\" for pod myapp-deployment-abc123"),
                ("warn", "Failed to pull image \"myapp:v2.0\": rpc error: code = NotFound desc = failed to pull and unpack image"),
                ("error", "Error: ErrImagePull - failed to resolve reference \"myapp:v2.0\": not found"),
                ("info", "Back-off pulling image \"myapp:v2.0\""),
                ("warn", "Pod myapp-deployment-abc123 status: ImagePullBackOff"),
                ("error", "ImagePullBackOff: repository myapp not found: does not exist or no pull access"),
            ]
        },
        {
            "service": "kubelet",
            "scenario": "oom-killed",
            "logs": [
                ("info", "Pod monitoring/prometheus-0 started"),
                ("warn", "Memory usage of container prometheus exceeds 90% of limit"),
                ("error", "Container prometheus in pod prometheus-0 was killed (OOMKilled)"),
                ("error", "OOMKilled: container prometheus out of memory, exit code 137"),
                ("warn", "Pod prometheus-0 restarted due to OOMKill"),
                ("info", "Restarting container prometheus (restart count: 2)"),
                ("error", "Pod monitoring/prometheus-0 status: OOMKilled - memory limit exceeded"),
            ]
        },
        {
            "service": "kube-controller-manager",
            "scenario": "pvc-pending",
            "logs": [
                ("info", "Provisioning PVC \"data-pvc\" in namespace \"default\""),
                ("warn", "Failed to provision volume with StorageClass \"slow\": volume not found"),
                ("error", "PVC default/data-pvc is in Pending state: no persistent volumes available"),
                ("warn", "Provisioning failed, waiting for retry (5m0s)"),
                ("error", "PersistentVolumeClaim is not bound: \"data-pvc\""),
                ("info", "Pod mysql-0 waiting for PVC data-pvc to be bound"),
            ]
        },
        {
            "service": "kube-apiserver",
            "scenario": "rbac-denied",
            "logs": [
                ("warn", "Forbidden: user \"dev-user\" cannot list pods in namespace \"kube-system\""),
                ("error", "RBAC: access denied - user dev-user is not allowed to get configmaps in default namespace"),
                ("warn", "configmaps is forbidden: User \"svc-account\" cannot list resource in API group \"\" in the namespace \"prod\""),
                ("error", "ClusterRole \"pod-reader\" does not exist"),
                ("warn", "ServiceAccount \"my-sa\" not found in namespace \"default\""),
            ]
        },
        {
            "service": "kube-scheduler",
            "scenario": "node-not-ready",
            "logs": [
                ("info", "Node worker-node-1 status updated"),
                ("warn", "Node worker-node-1 condition Ready is Unknown"),
                ("error", "Node worker-node-1 is NotReady - kubelet stopped posting node status"),
                ("warn", "Pod eviction triggered for node worker-node-1"),
                ("error", "FailedScheduling: 0/3 nodes are available: 1 node(s) were not ready, 2 node(s) had taint"),
                ("info", "Evicting pods from node worker-node-1"),
            ]
        },
        {
            "service": "coredns",
            "scenario": "dns-failure",
            "logs": [
                ("warn", "DNS resolution failed for service \"database.default.svc.cluster.local\""),
                ("error", "no such host: lookup mysql-service on 10.96.0.10:53: server misbehaving"),
                ("warn", "CoreDNS plugin errors: plugin/forward: no endpoints available"),
                ("error", "DNS lookup timeout after 5s for service redis.default.svc.cluster.local"),
                ("warn", "SERVFAIL response from upstream DNS for cluster.local"),
            ]
        },
        {
            "service": "etcd",
            "scenario": "etcd-issues",
            "logs": [
                ("warn", "etcd member 12345 slow fdatasync took 350ms"),
                ("error", "etcdserver: request timed out after 5s"),
                ("warn", "wal sync duration too high: 250ms (threshold: 100ms)"),
                ("error", "leader changed, proposal failed: no leader"),
                ("warn", "etcd cluster latency is high, 3/5 members > 100ms RTT"),
            ]
        },
        {
            "service": "ingress-nginx",
            "scenario": "ingress-error",
            "logs": [
                ("warn", "Ingress rules with conflicting hosts detected"),
                ("error", "Failed to list *v1.Ingress: ingresses.networking.k8s.io is forbidden"),
                ("warn", "Service \"backend-svc\" does not have any active Endpoint"),
                ("error", "503 Service Temporarily Unavailable - no endpoints available for service"),
                ("warn", "SSL certificate for domain \"example.com\" expired"),
            ]
        },
        {
            "service": "kubelet",
            "scenario": "configmap-missing",
            "logs": [
                ("warn", "ConfigMap \"app-config\" not found in namespace \"default\""),
                ("error", "Pod app-pod-xyz failed to start: configmap \"app-config\" not found"),
                ("warn", "Couldn't find key DATABASE_URL in ConfigMap default/app-config"),
                ("error", "CreateContainerConfigError: configmap \"app-config\" not found"),
                ("info", "Pod app-pod-xyz status: CreateContainerConfigError"),
            ]
        },
        {
            "service": "kubelet",
            "scenario": "liveness-probe-fail",
            "logs": [
                ("info", "Pod api-server started"),
                ("warn", "Liveness probe failed: Get \"http://10.244.1.5:8080/health\": dial tcp 10.244.1.5:8080: connect: connection refused"),
                ("error", "Container api-server failed liveness probe, will be restarted"),
                ("warn", "Liveness probe failed 3 times consecutively"),
                ("error", "Container api-server is unhealthy - restarting"),
                ("info", "Restarted container api-server"),
            ]
        },
        {
            "service": "apiserver",
            "scenario": "cert-expired",
            "logs": [
                ("error", "x509: certificate has expired or is not yet valid"),
                ("warn", "TLS handshake error from 10.0.0.5: certificate expired"),
                ("error", "Failed to verify client certificate: x509: certificate has expired"),
                ("warn", "ServiceAccount token is expired"),
                ("error", "Unable to authenticate the request due to an error: x509: certificate is expired"),
            ]
        },
    ]

    current_time = base_time

    for scenario in scenarios:
        svc = scenario["service"]
        for level, msg in scenario["logs"]:
            current_time += timedelta(seconds=random.randint(5, 30))
            timestamp = current_time.strftime("%Y-%m-%dT%H:%M:%S")
            logs.append({
                "level": level,
                "message": msg,
                "service": svc,
                "source": "k8s-demo",
                "timestamp": timestamp,
                "tags": f"k8s,{scenario['scenario']}",
            })

        current_time += timedelta(minutes=random.randint(2, 6))

    extra_info_logs = [
        ("kubelet", "info", "Pod kube-system/coredns-abc123 scheduled successfully"),
        ("kubelet", "info", "Successfully created container pause"),
        ("kube-apiserver", "info", "kube-apiserver started successfully"),
        ("kube-controller-manager", "info", "Starting deployment controller"),
        ("kube-scheduler", "info", "Scheduler is healthy"),
        ("coredns", "info", "CoreDNS is ready"),
        ("etcd", "info", "etcd server is ready to serve client requests"),
        ("ingress-nginx", "info", "NGINX Ingress controller started"),
        ("kubelet", "info", "Node master-1 Ready"),
        ("kubelet", "info", "Node worker-node-2 Ready"),
        ("kubelet", "info", "Volume mounted successfully"),
        ("kube-apiserver", "info", "Authentication succeeded for user system:serviceaccount"),
        ("kubelet", "info", "Container started successfully"),
        ("kubelet", "info", "Pulling image \"nginx:latest\""),
        ("kubelet", "info", "Successfully pulled image \"nginx:latest\" in 3.2s"),
        ("kube-controller-manager", "info", "Deployment nginx successfully rolled out"),
        ("kube-scheduler", "info", "Successfully assigned default/nginx to worker-node-1"),
        ("kubelet", "info", "SyncLoop RUN"),
        ("kubelet", "info", "Pod worker-node-1 status: Running"),
        ("kubelet", "info", "Network plugin is ready"),
    ]

    for svc, level, msg in extra_info_logs:
        t = base_time + timedelta(seconds=random.randint(0, 1800))
        logs.append({
            "level": level,
            "message": msg,
            "service": svc,
            "source": "k8s-demo",
            "timestamp": t.strftime("%Y-%m-%dT%H:%M:%S"),
            "tags": "k8s,normal",
        })

    logs.sort(key=lambda x: x["timestamp"])

    return logs

def main():
    print("=" * 60)
    print("  生成 K8s 场景测试日志")
    print("=" * 60)

    print("\n[1/3] 生成日志数据...")
    logs = generate_k8s_logs()
    print(f"  共生成 {len(logs)} 条日志")

    level_counts = {}
    for log in logs:
        lvl = log["level"]
        level_counts[lvl] = level_counts.get(lvl, 0) + 1
    print(f"  级别分布: {level_counts}")

    print("\n[2/3] 分批发送到 LogInsight...")
    batch_size = 50
    for i in range(0, len(logs), batch_size):
        batch = logs[i:i+batch_size]
        send_logs(batch)
        print(f"  已发送 {min(i+batch_size, len(logs))}/{len(logs)}")
        time.sleep(0.5)

    print("\n[3/3] 等待数据落库...")
    time.sleep(2)

    print("\n" + "=" * 60)
    print("  完成！K8s 场景日志已注入")
    print("=" * 60)
    print(f"\n  访问 http://localhost:8000/ 查看效果")
    print(f"  共 {len(logs)} 条日志，包含以下场景：")
    scenarios = [
        "CrashLoopBackOff（容器崩溃循环重启）",
        "ImagePullBackOff（镜像拉取失败）",
        "OOMKilled（内存溢出）",
        "PVC Pending（持久卷挂起）",
        "RBAC 权限拒绝",
        "Node NotReady（节点不就绪）",
        "DNS 解析失败",
        "etcd 性能问题",
        "Ingress 503错误",
        "ConfigMap 缺失",
        "Liveness Probe 失败",
        "证书过期",
    ]
    for s in scenarios:
        print(f"    - {s}")
    print("\n  点击任意 ERROR 日志即可触发 AI 分析")
    print("=" * 60)

if __name__ == "__main__":
    main()
