#
quitjobs() {
  echo ""
  pkill -P $$
  echo "Killed all running jobs".
  scriptCancelled="true"
  trap - INT
  exit
}
trap quitjobs INT

kubectl port-forward svc/frontend 8080:8080 &
kubectl port-forward svc/grafana 3000:3000 &
kubectl port-forward svc/prometheus 9090:9090 &
kubectl port-forward svc/jaeger 16686:16686
