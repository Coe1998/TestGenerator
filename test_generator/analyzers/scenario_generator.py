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

    def analyze_source_file(self, file_path: Path):
        """
        Punto di ingresso unico: analizza il file, risolve interfacce 
        e restituisce (lista_scenari, codice_completo).
        """
        main_content = file_path.read_text(encoding="utf-8")
        main_bytes = main_content.encode("utf-8")
        tree = self.parser.parse(main_bytes)
        
        # 1. Scenari del file principale
        scenarios = set()
        self._visit_iterative(tree.root_node, main_bytes, scenarios)
        
        # 2. Risoluzione Interfacce
        full_content = main_content
        iface_names = self.find_interfaces(tree.root_node, main_bytes)
        
        for iface in iface_names:
            # Cerchiamo il file dell'interfaccia nella stessa cartella
            iface_path = file_path.parent / f"{iface}.cs"
            if iface_path.exists():
                try:
                    if_src = iface_path.read_text(encoding="utf-8")
                    if_bytes = if_src.encode("utf-8")
                    if_tree = self.parser.parse(if_bytes)
                    
                    if_scenarios = set()
                    self._visit_iterative(if_tree.root_node, if_bytes, if_scenarios)
                    
                    # Tagghiamo gli scenari dell'interfaccia per distinguerli
                    for s in if_scenarios:
                        s.method_context = f"{s.method_context} [{iface}]" if s.method_context else iface
                    
                    scenarios.update(if_scenarios)
                    full_content += f"\n\n// --- INTERFACE: {iface} ---\n{if_src}"
                except Exception as e:
                    print(f"  [WARN] Errore analisi interfaccia {iface}: {e}")

        sorted_scenarios = sorted(scenarios, key=lambda s: (s.method_context or "", s.category))
        return sorted_scenarios, full_content

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
                            # Convenzione C# per interfacce: I + Maiuscola
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

            handler = getattr(self, f"_handle_{node.type}", None)
            if handler:
                handler(node, code_bytes, scenarios, method_ctx)

            for child in reversed(node.children):
                stack.append((child, method_ctx))

    # ===============================
    # HANDLERS (Semplificati)
    # ===============================

    def _handle_method_declaration(self, node, code_bytes, scenarios, method_ctx):
        mod_node = node.child_by_field_name("modifiers")
        modifiers = self._get_text(mod_node, code_bytes)
        if modifiers and "public" in modifiers:
            ret_type = self._get_text(node.child_by_field_name("type"), code_bytes)
            msg = f"Verificare valore ritorno '{method_ctx}'." if ret_type != "void" else f"Verificare side-effects '{method_ctx}'."
            cat = "OUTPUT" if ret_type != "void" else "SIDE_EFFECT"
            scenarios.add(Scenario(cat, msg, method_ctx))

    def _handle_if_statement(self, node, code_bytes, scenarios, method_ctx):
        cond = self._get_text(node.child_by_field_name("condition"), code_bytes)
        scenarios.add(Scenario("LOGIC", f"Testare ramo TRUE/FALSE di: {cond}", method_ctx))

    def _handle_throw_statement(self, node, code_bytes, scenarios, method_ctx):
        scenarios.add(Scenario("EXCEPTION", f"Verificare lancio: {self._get_text(node, code_bytes).strip()}", method_ctx))

    def _handle_parameter(self, node, code_bytes, scenarios, method_ctx):
        p_type = self._get_text(node.child_by_field_name("type"), code_bytes)
        p_name = self._get_text(node.child_by_field_name("name"), code_bytes)
        if not p_type or not p_name: return

        if "string" in p_type.lower():
            scenarios.add(Scenario("INPUT", f"Parametro '{p_name}': testare Null/Empty/Whitespace.", method_ctx))
        elif not self._is_primitive(p_type.replace("?", "")):
            scenarios.add(Scenario("INPUT", f"Oggetto '{p_name}': testare se NULL.", method_ctx))

    def _handle_binary_expression(self, node, code_bytes, scenarios, method_ctx):
        if any(op in self._get_text(node, code_bytes) for op in ["<", ">", "==", "!="]):
            scenarios.add(Scenario("BOUNDARY", f"Testare limiti di: {self._get_text(node, code_bytes)}", method_ctx))

    def _get_text(self, node, code_bytes):
        return code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore") if node else ""

    def _is_primitive(self, t):
        return t.lower() in {"int", "bool", "decimal", "double", "float", "long", "datetime", "guid", "char"}