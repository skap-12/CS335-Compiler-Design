import copy
import networkx as nx
from networkx.drawing.nx_pydot import to_pydot
from lattice import Lattice, TransferFunction
import ChironAST.ChironAST as ChironAST

# ==========================================
# Phase 2: Def-Use Extraction Helper
# ==========================================

def get_def_use(ast_node):
    """Recursively extracts variables defined and used by an AST node."""
    defs = set()
    uses = set()
    
    if isinstance(ast_node, ChironAST.AssignmentCommand):
        defs.add(str(ast_node.lvar))
        _, rhs_uses = get_def_use(ast_node.rexpr)
        uses.update(rhs_uses)
        
    elif isinstance(ast_node, (ChironAST.BinArithOp, ChironAST.BinCondOp, ChironAST.AND, ChironAST.OR, ChironAST.LT, ChironAST.GT, ChironAST.LTE, ChironAST.GTE, ChironAST.EQ, ChironAST.NEQ, ChironAST.Sum, ChironAST.Diff, ChironAST.Mult, ChironAST.Div)):
        _, l_uses = get_def_use(ast_node.lexpr)
        _, r_uses = get_def_use(ast_node.rexpr)
        uses.update(l_uses)
        uses.update(r_uses)
        
    elif isinstance(ast_node, (ChironAST.UnaryArithOp, ChironAST.UMinus, ChironAST.NOT)):
        _, e_uses = get_def_use(ast_node.expr)
        uses.update(e_uses)
        
    elif isinstance(ast_node, ChironAST.Var):
        uses.add(str(ast_node.varname))
        
    elif isinstance(ast_node, ChironAST.ConditionCommand):
        _, c_uses = get_def_use(ast_node.cond)
        uses.update(c_uses)
        
    elif isinstance(ast_node, ChironAST.MoveCommand):
        _, e_uses = get_def_use(ast_node.expr)
        uses.update(e_uses)
        
    return defs, uses

# ==========================================
# Phase 3: Data Dependencies (Reaching Defs)
# ==========================================

class ReachingDefDomain(Lattice):
    def __init__(self, data=None):
        self.defs = set(data) if data else set()

    def meet(self, other):
        return ReachingDefDomain(self.defs.union(other.defs))

    def __eq__(self, other):
        return self.defs == other.defs

class ReachingDefTransferFunction(TransferFunction):
    def transferFunction(self, currBBIN, currBB):
        out_dict = copy.deepcopy(currBBIN) if currBBIN else {}
        
        for instr, ir_idx in currBB.instrlist:
            defs, _ = get_def_use(instr)
            for d in defs:
                out_dict[d] = ReachingDefDomain({ir_idx}) 
                
        if len(currBB.instrlist) > 0 and isinstance(currBB.instrlist[-1][0], ChironAST.ConditionCommand):
            return [out_dict, out_dict]
        return [out_dict]

class ReachingDefAnalysis():
    def __init__(self):
        self.transferFunctionInstance = ReachingDefTransferFunction()
        
    def initialize(self, currBB, isStartNode):
        return {} 

    def isEqual(self, dA, dB):
        if set(dA.keys()) != set(dB.keys()): return False
        for k in dA.keys():
            if not (dA[k] == dB[k]): return False
        return True

    def meet(self, predList):
        meetVal = {}
        for pred_dict in predList:
            for var_name, def_domain in pred_dict.items():
                if var_name not in meetVal:
                    meetVal[var_name] = ReachingDefDomain(def_domain.defs)
                else:
                    meetVal[var_name] = meetVal[var_name].meet(def_domain)
        return meetVal

# ==========================================
# Phase 4: Data Dependence Graph (DDG)
# ==========================================

class ChironDDG:
    def __init__(self, irHandler):
        self.ddg = nx.DiGraph(name="Data_Dependence_Graph")
        self.irHandler = irHandler
        self._build_graph()

    def _compute_reaching_defs_worklist(self):
        """Standalone Worklist Algorithm bypassing the framework bug."""
        cfg = self.irHandler.cfg
        analysis = ReachingDefAnalysis()
        
        bbIn = {node.name: analysis.initialize(node, node.name == "START") for node in cfg.nodes()}
        bbOut = {node.name: [] for node in cfg.nodes()}
        
        worklist = list(cfg.nodes())
        
        while worklist:
            currBB = worklist.pop(0)
            if currBB.name == "END": continue
            
            # Meet over predecessors
            inlist = []
            for pred in cfg.predecessors(currBB):
                label = cfg.get_edge_label(pred, currBB)
                out_vals = bbOut[pred.name]
                if out_vals:
                    if label != 'Cond_False':
                        inlist.append(out_vals[0])
                    elif len(out_vals) > 1:
                        inlist.append(out_vals[1])
            
            if inlist:
                bbIn[currBB.name] = analysis.meet(inlist)
                
            # Transfer
            oldOut = bbOut[currBB.name]
            newOut = analysis.transferFunctionInstance.transferFunction(bbIn[currBB.name], currBB)
            bbOut[currBB.name] = newOut
            
            # Check for changes
            changed = False
            if len(oldOut) != len(newOut):
                changed = True
            else:
                for old_v, new_v in zip(oldOut, newOut):
                    if not analysis.isEqual(old_v, new_v):
                        changed = True
                        break
                        
            # If changed, add successors back to worklist
            if changed:
                for succ in cfg.successors(currBB):
                    if succ not in worklist:
                        worklist.append(succ)
                        
        return bbIn

    def _build_graph(self):
        # 1. Add all instructions as nodes
        for idx, (instr, jump) in enumerate(self.irHandler.ir):
            self.ddg.add_node(idx, instruction=instr)

        # 2. Reaching Definitions
        bbIn = self._compute_reaching_defs_worklist()

        # 3. Draw ONLY Data Dependence Edges
        for bb in self.irHandler.cfg:
            curr_state = {k: set(v.defs) for k, v in bbIn[bb.name].items()}
            
            for instr, ir_idx in bb.instrlist:
                defs, uses = get_def_use(instr)
                
                # Draw edges for used variables
                for use_var in uses:
                    if use_var in curr_state:
                        for def_idx in curr_state[use_var]:
                            self.ddg.add_edge(def_idx, ir_idx, type='data', var=use_var)
                
                # Update state with new definitions
                for d in defs:
                    curr_state[d] = {ir_idx}


# ==========================================
# Output: Draw the DDG
# ==========================================

def dump_ddg(ddg_wrapper, irHandler, filename="ddg_output"):
    """Dumps a pure Data Dependency Graph to a visual file."""
    G = ddg_wrapper.ddg.copy()

    # Style nodes
    for node in list(G.nodes()):
        instr = irHandler.ir[node][0]
        
        # Filter out internal framework counters if present
        if "__rep_counter_" in str(instr):
            G.remove_node(node)
            continue
            
        line_no = getattr(instr, 'line_number', '?')
        G.nodes[node]['label'] = f"L{node} (Line {line_no}):\n{instr}"
        G.nodes[node]['shape'] = 'box'
        G.nodes[node]['style'] = 'filled'
        G.nodes[node]['color'] = 'lightgray'
        G.nodes[node]['fillcolor'] = '#f8f9fa'
        G.nodes[node]['fontcolor'] = 'black'

    # Style data edges
    for u, v, data in G.edges(data=True):
        if data.get('type') == 'data':
            data['color'] = 'blue'
            data['label'] = f"data ({data.get('var', '')})"

    # Draw graph
    P = to_pydot(G)
    P.write_png(filename + ".png")