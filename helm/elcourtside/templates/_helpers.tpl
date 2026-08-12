{{- define "elcourtside.labels" -}}
app.kubernetes.io/name: elcourtside
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/* Per-component selector: the two Deployments must not select each other. */}}
{{- define "elcourtside.componentLabels" -}}
app.kubernetes.io/name: elcourtside
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}
