from collections import deque
from pathlib import Path
from tree_sitter import Parser
from config import CS_LANG, SEVERITY_MAP

class Scenario:
    def __init__(self, category, message, method_context=None):
        self.category = category
        self.message = message
        self.severity = SEVERITY_MAP.get(category, "MEDIUM")
        self.method_context = method_context

    def __hash__(self):
        return hash((self.category, self.message, self.method_context))

    def __eq__(self, other):
        return (isinstance(other, Scenario) and
                (self.category, self.message, self.method_context) ==
                (other.category, other.message, other.method_context))

    def to_dict(self):
        return {
            "category": self.category, "severity": self.severity,
            "method_context": self.method_context, "message": self.message
        }


class ScenarioGenerator:
    def __init__(self):
        self.parser = Parser(CS_LANG)

    # ---------------------------------------------------------------------------
    # Entry point
    # ---------------------------------------------------------------------------

    def analyze_source_file(self, file_path: Path):
        """
        Punto di ingresso unico: analizza il file, risolve interfacce
        e restituisce (lista_scenari, codice_completo).
        """
        main_content = file_path.read_text(encoding="utf-8")
        main_bytes = main_content.encode("utf-8")
        tree = self.parser.parse(main_bytes)

        scenarios = set()
        self._visit_iterative(tree.root_node, main_bytes, scenarios)

        full_content = main_content
        iface_names = self.find_interfaces(tree.root_node, main_bytes)

        for iface in iface_names:
            iface_path = self._find_interface_file(iface, file_path.parent)
            if iface_path:
                try:
                    if_src = iface_path.read_text(encoding="utf-8")
                    if_bytes = if_src.encode("utf-8")
                    if_tree = self.parser.parse(if_bytes)

                    if_scenarios = set()
                    self._visit_iterative(if_tree.root_node, if_bytes, if_scenarios)

                    for s in if_scenarios:
                        s.method_context = f"{s.method_context} [{iface}]" if s.method_context else iface

                    scenarios.update(if_scenarios)
                    full_content += f"\n\n// --- INTERFACE: {iface} ---\n{if_src}"
                except Exception as e:
                    print(f"  [WARN] Errore analisi interfaccia {iface}: {e}")

        sorted_scenarios = sorted(scenarios, key=lambda s: (s.method_context or "", s.category))
        return sorted_scenarios, full_content

    # ---------------------------------------------------------------------------
    # Ricerca interfacce estesa
    # ---------------------------------------------------------------------------

    def _find_interface_file(self, iface: str, start_dir: Path) -> Path | None:
        """
        Cerca il file .cs dell'interfaccia partendo dalla cartella del file sorgente.
        Guarda nella stessa cartella, nelle sottocartelle comuni e risale di livello.
        """
        common_subdirs = ("Interfaces", "Abstractions", "Contracts", "Core", "Domain")

        search_dirs: list[Path] = [start_dir]
        for sub in common_subdirs:
            search_dirs.append(start_dir / sub)

        ptr = start_dir.parent
        for _ in range(3):
            if ptr == ptr.parent:
                break
            search_dirs.append(ptr)
            for sub in common_subdirs:
                search_dirs.append(ptr / sub)
            ptr = ptr.parent

        for d in search_dirs:
            candidate = d / f"{iface}.cs"
            if candidate.exists():
                return candidate
        return None

    # ---------------------------------------------------------------------------
    # Visita AST
    # ---------------------------------------------------------------------------

    def find_interfaces(self, root_node, code_bytes):
        interfaces = []
        stack = deque([root_node])
        while stack:
            node = stack.pop()
            if node.type == "class_declaration":
                base_list = node.child_by_field_name("bases")
                if base_list:
                    for base in base_list.children:
                        if base.type == "simple_base_type":
                            name = self._get_text(base, code_bytes).strip()
                            if len(name) > 1 and name[0] == "I" and name[1].isupper():
                                interfaces.append(name)
            for child in reversed(node.children):
                stack.append(child)
        return interfaces

    def _visit_iterative(self, root, code_bytes, scenarios):
        stack = deque([(root, None)])
        while stack:
            node, method_ctx = stack.pop()

            if node.type == "method_declaration":
                name_node = node.child_by_field_name("name")
                method_ctx = self._get_text(name_node, code_bytes) if name_node else None
            elif node.type == "constructor_declaration":
                name_node = node.child_by_field_name("name")
                ctor_name = self._get_text(name_node, code_bytes) if name_node else "ctor"
                method_ctx = f".ctor({ctor_name})"

            handler = getattr(self, f"_handle_{node.type}", None)
            if handler:
                handler(node, code_bytes, scenarios, method_ctx)

            for child in reversed(node.children):
                stack.append((child, method_ctx))

    # ---------------------------------------------------------------------------
    # HANDLERS
    # ---------------------------------------------------------------------------

    def _handle_method_declaration(self, node, code_bytes, scenarios, method_ctx):
        mod_node = node.child_by_field_name("modifiers")
        modifiers = self._get_text(mod_node, code_bytes)
        if modifiers and "public" in modifiers:
            ret_type = self._get_text(node.child_by_field_name("type"), code_bytes)
            msg = (f"Verificare valore ritorno '{method_ctx}'."
                   if ret_type != "void" else f"Verificare side-effects '{method_ctx}'.")
            cat = "OUTPUT" if ret_type != "void" else "SIDE_EFFECT"
            scenarios.add(Scenario(cat, msg, method_ctx))
        # Metodo async → pattern di test asincrono
        if modifiers and "async" in modifiers:
            scenarios.add(Scenario("ASYNC",
                f"Verificare completamento asincrono di '{method_ctx}'.", method_ctx))

    def _handle_constructor_declaration(self, node, code_bytes, scenarios, method_ctx):
        """Ogni parametro non-primitivo del costruttore deve essere testato con null."""
        params = node.child_by_field_name("parameters")
        if not params:
            return
        for child in params.children:
            if child.type == "parameter":
                p_type = self._get_text(child.child_by_field_name("type"), code_bytes)
                p_name = self._get_text(child.child_by_field_name("name"), code_bytes)
                if p_name and p_type and not self._is_primitive(p_type.replace("?", "")):
                    scenarios.add(Scenario("CONSTRUCTOR",
                        f"Costruttore: verificare che '{p_name}' null lanci ArgumentNullException.",
                        method_ctx))

    def _handle_if_statement(self, node, code_bytes, scenarios, method_ctx):
        cond = self._get_text(node.child_by_field_name("condition"), code_bytes)
        scenarios.add(Scenario("LOGIC", f"Testare ramo TRUE/FALSE di: {cond}", method_ctx))

    def _handle_switch_statement(self, node, code_bytes, scenarios, method_ctx):
        val = self._get_text(node.child_by_field_name("value"), code_bytes)
        sections = [c for c in node.children if c.type == "switch_section"]
        n = len(sections)
        label = f" ({n} casi)" if n else ""
        scenarios.add(Scenario("LOGIC",
            f"Testare tutti i casi dello switch{label} su: {val}", method_ctx))

    def _handle_switch_expression(self, node, code_bytes, scenarios, method_ctx):
        val = self._get_text(node.child_by_field_name("value"), code_bytes)
        arms = [c for c in node.children if c.type == "switch_expression_arm"]
        n = len(arms)
        label = f" ({n} arms)" if n else ""
        scenarios.add(Scenario("LOGIC",
            f"Testare tutti gli arms della switch expression{label} su: {val}", method_ctx))

    def _handle_throw_statement(self, node, code_bytes, scenarios, method_ctx):
        scenarios.add(Scenario("EXCEPTION",
            f"Verificare lancio: {self._get_text(node, code_bytes).strip()}", method_ctx))

    def _handle_parameter(self, node, code_bytes, scenarios, method_ctx):
        p_type = self._get_text(node.child_by_field_name("type"), code_bytes)
        p_name = self._get_text(node.child_by_field_name("name"), code_bytes)
        if not p_type or not p_name:
            return
        if "string" in p_type.lower():
            scenarios.add(Scenario("INPUT",
                f"Parametro '{p_name}': testare Null/Empty/Whitespace.", method_ctx))
        elif not self._is_primitive(p_type.replace("?", "")):
            scenarios.add(Scenario("INPUT",
                f"Oggetto '{p_name}': testare se NULL.", method_ctx))

    def _handle_binary_expression(self, node, code_bytes, scenarios, method_ctx):
        text = self._get_text(node, code_bytes)
        if any(op in text for op in ["<", ">", "==", "!="]):
            scenarios.add(Scenario("BOUNDARY", f"Testare limiti di: {text}", method_ctx))
        # Null-coalescing operator ??
        for child in node.children:
            if self._get_text(child, code_bytes).strip() == "??":
                scenarios.add(Scenario("NULL_SAFETY",
                    f"Testare valore di fallback (??): {text[:80]}", method_ctx))
                break

    def _handle_conditional_access_expression(self, node, code_bytes, scenarios, method_ctx):
        """Operatore ?. — testare il caso in cui l'oggetto sia null."""
        expr = self._get_text(node, code_bytes)
        scenarios.add(Scenario("NULL_SAFETY",
            f"Testare accesso condizionale (?.) quando oggetto è null: {expr[:80]}", method_ctx))

    # ---------------------------------------------------------------------------
    # Utilities
    # ---------------------------------------------------------------------------

    def _get_text(self, node, code_bytes):
        return (code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")
                if node else "")

    def _is_primitive(self, t):
        return t.lower() in {
            "int", "bool", "decimal", "double", "float", "long",
            "datetime", "guid", "char", "byte", "short", "uint",
            "ulong", "ushort", "sbyte",
        }