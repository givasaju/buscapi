from flows.ip_flow import IPAnalysisService

svc = IPAnalysisService()

# Inicia análise
qid = svc.start_analysis("blockchain supply chain patents")

# Executa todas as etapas (até análise)
res = svc.execute_analysis(qid)


# Inspecionar o relatório parcial
print("Classificação JSON:", res.get("classified_data"))
print("Resultados da análise:", res.get("analysis_results"))
print("Visualizações:", res.get("visualizations"))
print("Final Report keys:", res.keys())
