import json
import urllib.request
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

def generate_node_failure_logs():
    now = datetime.now()
    base_time = now - timedelta(minutes=15)
    logs = []
    t = base_time

    scenario_logs = [
        # ==== kubelet 节点异常 ====
        ("kubelet", "worker-node-03", "error",
         "Failed to create pod sandbox: rpc error: code = Unknown desc = failed to setup network for sandbox: plugin type=\"calico\" failed (add): error getting ClusterInformation: connection is unauthorized: Unauthorized"),
        ("kubelet", "worker-node-03", "warn",
         "CNI plugin failed: networkPlugin cni failed to set up pod \"nginx-deployment-7f9b8d6c5-klm2p_default\" network: plugin type=\"calico\" failed"),
        ("kubelet", "worker-node-03", "error",
         "Pod sandbox changed, it will be killed and re-created."),
        ("kubelet", "worker-node-03", "error",
         "Failed to create pod sandbox: rpc error: code = Unknown desc = failed to setup network for sandbox"),
        ("kubelet", "worker-node-03", "warn",
         "SyncLoop (PLEG): event for pod which cannot be found: default/nginx-deployment-7f9b8d6c5-klm2p"),

        # ==== calico-node DaemonSet ====
        ("calico-node", "kube-system", "error",
         "Unable to establish connection to Calico backend: connection refused"),
        ("calico-node", "kube-system", "error",
         "bird: BGP session not established with peer 10.244.0.1 (state: Active)"),
        ("calico-node", "kube-system", "warn",
         "Felix has started with partial configuration; some features may be disabled"),
        ("calico-node", "kube-system", "error",
         "calico/node is not ready: BIRD is not ready: BGP not established with 10.244.0.1"),

        # ==== kube-proxy ====
        ("kube-proxy", "kube-system", "error",
         "Failed to list *v1.Service: Get \"https://10.96.0.1:443/api/v1/services?limit=500\": dial tcp 10.96.0.1:443: connect: connection refused"),
        ("kube-proxy", "kube-system", "warn",
         "can't set sysctl net/ipv4/vs/conntrack: open /proc/sys/net/ipv4/vs/conntrack: no such file or directory"),
        ("kube-proxy", "kube-system", "error",
         "Failed to retrieve node config: couldn't get node \"worker-node-03\": Get \"https://10.96.0.1:443/api/v1/nodes/worker-node-03\": dial tcp 10.96.0.1:443: connect: connection refused"),

        # ==== kube-controller-manager ====
        ("kube-controller-manager", "kube-system", "warn",
         "Node worker-node-03 is not ready: NodeStatusUnknown"),
        ("kube-controller-manager", "kube-system", "error",
         "Node controller is unable to update node status for worker-node-03"),
        ("kube-controller-manager", "kube-system", "warn",
         "Evicting pods from node worker-node-03 that are in non-terminal phase due to node NotReady"),
        ("kube-controller-manager", "kube-system", "info",
         "Pod default/nginx-deployment-7f9b8d6c5-klm2p marked for deletion due to node NotReady"),

        # ==== kube-scheduler ====
        ("kube-scheduler", "kube-system", "warn",
         "FailedScheduling: 0/4 nodes are available: 1 node(s) had taint {node.kubernetes.io/unreachable: }, that the pod didn't tolerate, 2 node(s) were unschedulable, 1 Insufficient cpu."),
        ("kube-scheduler", "kube-system", "error",
         "Scheduling failed: no nodes available to schedule pods in namespace production"),

        # ==== 具体业务 Pod 报错 ====
        ("kubelet", "worker-node-03", "error",
         "Failed to start container \"api-server\" from image \"registry.example.com/prod/api-server:v2.3.1\": Error response from daemon: driver failed programming external connectivity on endpoint api-server"),
        ("kubelet", "worker-node-03", "error",
         "Pod production/api-server-58db7c4d9f-xzv2q status: CrashLoopBackOff (restart count: 7)"),
        ("kubelet", "worker-node-03", "warn",
         "Readiness probe failed: Get \"http://10.244.3.12:8080/health\": dial tcp 10.244.3.12:8080: connect: connection refused"),
        ("kubelet", "worker-node-03", "error",
         "Back-off restarting failed container api-server in pod api-server-58db7c4d9f-xzv2q_production"),

        # ==== coredns 报错 ====
        ("coredns", "kube-system", "error",
         "[ERROR] plugin/errors: 2 production.svc.cluster.local. A: read udp 10.244.3.2:34821->10.96.0.10:53: i/o timeout"),
        ("coredns", "kube-system", "warn",
         "Health check of upstream plugin failed: no endpoints available for service \"kube-dns\""),

        # ==== 节点状态相关 ====
        ("kube-apiserver", "kube-system", "warn",
         "Node worker-node-03 status updated to NotReady"),
        ("kubelet", "worker-node-03", "error",
         "Failed to list *v1.Pod: Get \"https://10.96.0.1:443/api/v1/pods?fieldSelector=spec.nodeName%3Dworker-node-03\": dial tcp 10.96.0.1:443: i/o timeout"),
        ("kubelet", "worker-node-03", "error",
         "Kubelet stopped posting node status: cannot update node status: Unauthorized"),
        ("kubelet", "worker-node-03", "warn",
         "Client connection broke: http2: client connection lost"),

        # ==== 一些 INFO 日志作为背景 ====
        ("kubelet", "worker-node-01", "info",
         "Node worker-node-01 status: Ready"),
        ("kubelet", "worker-node-02", "info",
         "Node worker-node-02 status: Ready"),
        ("kube-controller-manager", "kube-system", "info",
         "Deployment production/api-server successfully rolled out (revision 12)"),
        ("calico-node", "kube-system", "info",
         "Felix has started and is ready on worker-node-01"),
        ("kubelet", "worker-node-02", "info",
         "Pulling image \"registry.example.com/prod/api-server:v2.3.1\""),
        ("kubelet", "worker-node-02", "info",
         "Successfully pulled image \"registry.example.com/prod/api-server:v2.3.1\""),
        ("kube-scheduler", "kube-system", "info",
         "Successfully assigned production/api-server-58db7c4d9f-xzv2q to worker-node-03"),
    ]

    for service, source, level, message in scenario_logs:
        t += timedelta(seconds=random.randint(3, 20))
        timestamp = t.strftime("%Y-%m-%dT%H:%M:%S")

        tags = f"k8s,node-failure,worker-node-03,calico,crashloop"
        if level == "error":
            tags += ",error-scenario"

        logs.append({
            "level": level,
            "message": message,
            "service": service,
            "source": source,
            "timestamp": timestamp,
            "tags": tags,
        })

    logs.sort(key=lambda x: x["timestamp"])
    return logs

def main():
    print("=" * 60)
    print("  生成 K8s Node 节点故障场景日志")
    print("=" * 60)

    print("\n[1/2] 生成日志数据...")
    logs = generate_node_failure_logs()
    print(f"  共生成 {len(logs)} 条日志")

    level_counts = {}
    for log in logs:
        lvl = log["level"]
        level_counts[lvl] = level_counts.get(lvl, 0) + 1
    print(f"  级别分布: {level_counts}")

    print("\n[2/2] 发送到 LogInsight...")
    send_logs(logs)
    print(f"  已发送全部 {len(logs)} 条")

    print("\n" + "=" * 60)
    print("  完成！K8s Node 故障场景日志已注入")
    print("=" * 60)
    print(f"\n  场景：worker-node-03 节点 NotReady + Calico CNI 故障")
    print(f"  涉及命名空间：")
    print(f"    - kube-system (calico-node, kube-proxy, coredns)")
    print(f"    - production (api-server 业务Pod)")
    print(f"    - default (nginx 测试Pod)")
    print(f"\n  关键错误：")
    print(f"    - Calico CNI 插件失败，Pod 无法创建网络")
    print(f"    - kubelet 无法连接 apiserver (connection refused)")
    print(f"    - api-server Pod CrashLoopBackOff (重启7次)")
    print(f"    - worker-node-03 节点 NotReady")
    print(f"\n  建议测试：找到 production 命名空间的 ERROR 日志")
    print("=" * 60)

if __name__ == "__main__":
    main()
