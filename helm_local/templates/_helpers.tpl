{{- define "sds-middleware.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "sds-middleware.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name (include "sds-middleware.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "sds-middleware.labels" -}}
app.kubernetes.io/name: {{ include "sds-middleware.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "sds-middleware.selectorLabels" -}}
app.kubernetes.io/name: {{ include "sds-middleware.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
