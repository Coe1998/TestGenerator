FRAMEWORK_LABELS = {
    "mstest": "MSTest e FluentAssertions",
    "xunit": "xUnit e FluentAssertions",
    "nunit": "NUnit e FluentAssertions",
}

def build_prompt(scenarios, class_content, framework="mstest"):
    fw_label = FRAMEWORK_LABELS.get(framework.lower(), "MSTest e FluentAssertions")

    prompt = (
    f"Genera una classe di Unit Test in C# completa, usando {fw_label}, omettendo i [Description()], "
    "coprendo esattamente questi scenari raggruppati per metodo:\n\n"
    "REQUISITO CRITICO: Restituisci esclusivamente il codice sorgente. "
    "Non includere introduzioni, spiegazioni, commenti aggiuntivi o blocchi di testo Markdown (come ```csharp). "
    "L'output deve iniziare direttamente con gli 'using' e finire con l'ultima parentesi graffa.\n\n"
    )

    groups: dict[str, list] = {}
    for s in scenarios:
        key = s.method_context or "(contesto globale)"
        groups.setdefault(key, []).append(s)

    for method, group in groups.items():
        prompt += f"### Metodo: {method}\n"
        for i, s in enumerate(group, 1):
            prompt += f"  {i:02d}. [{s.category}] {s.message}\n"
        prompt += "\n"

    prompt += "=" * 40 + "\n"
    prompt += "CLASSE C# DA TESTARE:\n\n"
    prompt += class_content

    return prompt