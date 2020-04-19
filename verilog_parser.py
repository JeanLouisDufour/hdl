"""
 *
 *  This is the actual bison parser for Verilog code. The AST ist created directly
 *  from the bison reduce functions here. Note that this code uses a few global
 *  variables to hold the state of the AST generator and therefore this parser is
 *  not reentrant.
 *
"""
import ply # pour lex.LexError
import ply.yacc as yacc
import ply2yacc
# import functools
# tokens : Get the token map from the lexer.  This is required.
# lexer : permit to force yacc to use the good lexer (in case of multiple parsers)
from verilog_lexer import tokens, lexer

print('v38')

def make_seq_lr(p):
	""
	lp = len(p)
	if lp >= 3:
		p[1].append(p[lp-1])
		p[0] = p[1]
	elif lp >= 2:
		p[0] = [p[1]]
	else:
		p[0] = []
		
def make_seq_rr(p):
	""
	lp = len(p)
	if lp >= 3:
		p[0] = [p[1]]+p[lp-1]
	elif lp >= 2:
		p[0] = [p[1]]
	else:
		p[0] = []

"""
%{
#include <list>
#include <stack>
#include <string.h>
#include "frontends/verilog/verilog_frontend.h"
#include "frontends/verilog/verilog_parser.tab.hh"
#include "kernel/log.h"

#define YYLEX_PARAM &yylval, &yylloc

USING_YOSYS_NAMESPACE
using namespace AST;
using namespace VERILOG_FRONTEND;

YOSYS_NAMESPACE_BEGIN
namespace VERILOG_FRONTEND {
	int port_counter;
	std::map<std::string, int> port_stubs;
	std::map<std::string, AstNode*> *attr_list, default_attr_list;
	std::stack<std::map<std::string, AstNode*> *> attr_list_stack;
	std::map<std::string, AstNode*> *albuf;
	std::vector<UserTypeMap*> user_type_stack;
	std::map<std::string, AstNode*> pkg_user_types;
	std::vector<AstNode*> ast_stack;
	struct AstNode *astbuf1, *astbuf2, *astbuf3;
	struct AstNode *current_function_or_task;
	struct AstNode *current_ast, *current_ast_mod;
	int current_function_or_task_port_id;
	std::vector<char> case_type_stack;
	bool do_not_require_port_stubs;
	bool default_nettype_wire;
	bool sv_mode, formal_mode, lib_mode, specify_mode;
	bool noassert_mode, noassume_mode, norestrict_mode;
	bool assume_asserts_mode, assert_assumes_mode;
	bool current_wire_rand, current_wire_const;
	bool current_modport_input, current_modport_output;
	std::istream *lexin;
}
YOSYS_NAMESPACE_END

#define SET_AST_NODE_LOC(WHICH, BEGIN, END) \
    do { (WHICH)->location.first_line = (BEGIN).first_line; \
    (WHICH)->location.first_column = (BEGIN).first_column; \
    (WHICH)->location.last_line = (END).last_line; \
    (WHICH)->location.last_column = (END).last_column; } while(0)

#define SET_RULE_LOC(LHS, BEGIN, END) \
    do { (LHS).first_line = (BEGIN).first_line; \
    (LHS).first_column = (BEGIN).first_column; \
    (LHS).last_line = (END).last_line; \
    (LHS).last_column = (END).last_column; } while(0)

int frontend_verilog_yylex(YYSTYPE *yylval_param, YYLTYPE *yyloc_param);

static void append_attr(AstNode *ast, std::map<std::string, AstNode*> *al)
{
	for (auto &it : *al) {
		if (ast->attributes.count(it.first) > 0)
			delete ast->attributes[it.first];
		ast->attributes[it.first] = it.second;
	}
	delete al;
}

static void append_attr_clone(AstNode *ast, std::map<std::string, AstNode*> *al)
{
	for (auto &it : *al) {
		if (ast->attributes.count(it.first) > 0)
			delete ast->attributes[it.first];
		ast->attributes[it.first] = it.second->clone();
	}
}

static void free_attr(std::map<std::string, AstNode*> *al)
{
	for (auto &it : *al)
		delete it.second;
	delete al;
}

struct specify_target {
	char polarity_op;
	AstNode *dst, *dat;
};

struct specify_triple {
	AstNode *t_min, *t_avg, *t_max;
};

struct specify_rise_fall {
	specify_triple rise;
	specify_triple fall;
};

static void addTypedefNode(std::string *name, AstNode *node)
{
	log_assert(node);
	auto *tnode = new AstNode(AST_TYPEDEF, node);
	tnode->str = *name;
	auto user_types = user_type_stack.back();
	(*user_types)[*name] = tnode;
	if (current_ast_mod && current_ast_mod->type == AST_PACKAGE) {
		// typedef inside a package so we need the qualified name
		auto qname = current_ast_mod->str + "::" + (*name).substr(1);
		pkg_user_types[qname] = tnode;
	}
	delete name;
	ast_stack.back()->children.push_back(tnode);
}

static void enterTypeScope()
{
	auto user_types = new UserTypeMap();
	user_type_stack.push_back(user_types);
}

static void exitTypeScope()
{
	user_type_stack.pop_back();
}

static bool isInLocalScope(const std::string *name)
{
	// tests if a name was declared in the current block scope
	auto user_types = user_type_stack.back();
	return (user_types->count(*name) > 0);
}

static AstNode *makeRange(int msb = 31, int lsb = 0, bool isSigned = true)
{
	auto range = new AstNode(AST_RANGE);
	range->children.push_back(AstNode::mkconst_int(msb, true));
	range->children.push_back(AstNode::mkconst_int(lsb, true));
	range->is_signed = isSigned;
	return range;
}

static void addRange(AstNode *parent, int msb = 31, int lsb = 0, bool isSigned = true)
{
	auto range = makeRange(msb, lsb, isSigned);
	parent->children.push_back(range);
}
%}
"""
########
"""
%define api.prefix {frontend_verilog_yy}
%define api.pure

/* The union is defined in the header, so we need to provide all the
 * includes it requires
 */
%code requires {
#include <map>
#include <string>
#include "frontends/verilog/verilog_frontend.h"
}

%union {
	std::string *string;
	struct YOSYS_NAMESPACE_PREFIX AST::AstNode *ast;
	std::map<std::string, YOSYS_NAMESPACE_PREFIX AST::AstNode*> *al;
	struct specify_target *specify_target_ptr;
	struct specify_triple *specify_triple_ptr;
	struct specify_rise_fall *specify_rise_fall_ptr;
	bool boolean;
	char ch;
}

%token <string> TOK_STRING TOK_ID TOK_CONSTVAL TOK_REALVAL TOK_PRIMITIVE
%token <string> TOK_SVA_LABEL TOK_SPECIFY_OPER TOK_MSG_TASKS
%token <string> TOK_BASE TOK_BASED_CONSTVAL TOK_UNBASED_UNSIZED_CONSTVAL
%token <string> TOK_USER_TYPE TOK_PKG_USER_TYPE
%token TOK_ASSERT TOK_ASSUME TOK_RESTRICT TOK_COVER TOK_FINAL
%token ATTR_BEGIN ATTR_END DEFATTR_BEGIN DEFATTR_END
%token TOK_MODULE TOK_ENDMODULE TOK_PARAMETER TOK_LOCALPARAM TOK_DEFPARAM
%token TOK_PACKAGE TOK_ENDPACKAGE TOK_PACKAGESEP
%token TOK_INTERFACE TOK_ENDINTERFACE TOK_MODPORT TOK_VAR TOK_WILDCARD_CONNECT
%token TOK_INPUT TOK_OUTPUT TOK_INOUT TOK_WIRE TOK_WAND TOK_WOR TOK_REG TOK_LOGIC
%token TOK_INTEGER TOK_SIGNED TOK_ASSIGN TOK_ALWAYS TOK_INITIAL
%token TOK_ALWAYS_FF TOK_ALWAYS_COMB TOK_ALWAYS_LATCH
%token TOK_BEGIN TOK_END TOK_IF TOK_ELSE TOK_FOR TOK_WHILE TOK_REPEAT
%token TOK_DPI_FUNCTION TOK_POSEDGE TOK_NEGEDGE TOK_OR TOK_AUTOMATIC
%token TOK_CASE TOK_CASEX TOK_CASEZ TOK_ENDCASE TOK_DEFAULT
%token TOK_FUNCTION TOK_ENDFUNCTION TOK_TASK TOK_ENDTASK TOK_SPECIFY
%token TOK_IGNORED_SPECIFY TOK_ENDSPECIFY TOK_SPECPARAM TOK_SPECIFY_AND TOK_IGNORED_SPECIFY_AND
%token TOK_GENERATE TOK_ENDGENERATE TOK_GENVAR TOK_REAL
%token TOK_SYNOPSYS_FULL_CASE TOK_SYNOPSYS_PARALLEL_CASE
%token TOK_SUPPLY0 TOK_SUPPLY1 TOK_TO_SIGNED TOK_TO_UNSIGNED
%token TOK_POS_INDEXED TOK_NEG_INDEXED TOK_PROPERTY TOK_ENUM TOK_TYPEDEF
%token TOK_RAND TOK_CONST TOK_CHECKER TOK_ENDCHECKER TOK_EVENTUALLY
%token TOK_INCREMENT TOK_DECREMENT TOK_UNIQUE TOK_PRIORITY

%type <ast> range range_or_multirange  non_opt_range non_opt_multirange range_or_signed_int
%type <ast> wire_type expr basic_expr concat_list rvalue lvalue lvalue_concat_list
%type <string> opt_label opt_sva_label tok_prim_wrapper hierarchical_id hierarchical_type_id integral_number
%type <string> type_name
%type <ast> opt_enum_init
%type <boolean> opt_signed opt_property unique_case_attr always_comb_or_latch always_or_always_ff
%type <al> attr case_attr

%type <specify_target_ptr> specify_target
%type <specify_triple_ptr> specify_triple specify_opt_triple
%type <specify_rise_fall_ptr> specify_rise_fall
%type <ast> specify_if specify_condition
%type <ch> specify_edge

// operator precedence from low to high
%left OP_LOR
%left OP_LAND
%left '|' OP_NOR
%left '^' OP_XNOR
%left '&' OP_NAND
%left OP_EQ OP_NE OP_EQX OP_NEX
%left '<' OP_LE OP_GE '>'
%left OP_SHL OP_SHR OP_SSHL OP_SSHR
%left '+' '-'
%left '*' '/' '%'
%left OP_POW
%right UNARY_OPS

%define parse.error verbose
%define parse.lac full

%nonassoc FAKE_THEN
%nonassoc TOK_ELSE

%debug
%locations

%%

input: {
	ast_stack.clear();
	ast_stack.push_back(current_ast);
} design {
	ast_stack.pop_back();
	log_assert(GetSize(ast_stack) == 0);
	for (auto &it : default_attr_list)
		delete it.second;
	default_attr_list.clear();
};
"""
start = 'input'
def p_input(p):
	"input : design_STAR"
	p[0] = p[1]

"""
design:
	module design |
	defattr design |
	task_func_decl design |
	param_decl design |
	localparam_decl design |
	typedef_decl design |
	package design |
	interface design |
	/* empty */;
"""
def p_design(p):
	"""design : defattr
	| interface
	| module
	| package
	| PP_CELLDEFINE
	| PP_ENDCELLDEFINE
	| PP_RESETALL
	| PP_TIMESCALE TOK_CONSTVAL TOK_ID '/' TOK_CONSTVAL TOK_ID
	"""
	p[0] = p[1]

"""
attr:
	{
		if (attr_list != nullptr)
			attr_list_stack.push(attr_list);
		attr_list = new std::map<std::string, AstNode*>;
		for (auto &it : default_attr_list)
			(*attr_list)[it.first] = it.second->clone();
	} attr_opt {
		$$ = attr_list;
		if (!attr_list_stack.empty()) {
			attr_list = attr_list_stack.top();
			attr_list_stack.pop();
		} else
			attr_list = nullptr;
	};

attr_opt:
	attr_opt ATTR_BEGIN opt_attr_list ATTR_END {
		SET_RULE_LOC(@$, @2, @$);
	}|
	/* empty */;
"""
def p_attr(p):
	"""attr : ATTR_BEGIN attr_assign_SEQ_OPT ATTR_END
	"""
	p[0] = None
	
"""
defattr:
	DEFATTR_BEGIN {
		if (attr_list != nullptr)
			attr_list_stack.push(attr_list);
		attr_list = new std::map<std::string, AstNode*>;
		for (auto &it : default_attr_list)
			delete it.second;
		default_attr_list.clear();
	} opt_attr_list {
		attr_list->swap(default_attr_list);
		delete attr_list;
		if (!attr_list_stack.empty()) {
			attr_list = attr_list_stack.top();
			attr_list_stack.pop();
		} else
			attr_list = nullptr;
	} DEFATTR_END;
"""
def p_defattr(p):
	"""defattr : DEFATTR_BEGIN attr_assign_SEQ_OPT DEFATTR_END
	"""
	p[0] = None
"""
opt_attr_list:
	attr_list | /* empty */;

attr_list:
	attr_assign |
	attr_list ',' attr_assign;

attr_assign:
	hierarchical_id {
		if (attr_list->count(*$1) != 0)
			delete (*attr_list)[*$1];
		(*attr_list)[*$1] = AstNode::mkconst_int(1, false);
		delete $1;
	} |
	hierarchical_id '=' expr {
		if (attr_list->count(*$1) != 0)
			delete (*attr_list)[*$1];
		(*attr_list)[*$1] = $3;
		delete $1;
	};
"""
def p_attr_assign(p):
	"""attr_assign : hierarchical_id
	| hierarchical_id '=' expr
	"""
	p[0] = None
"""
hierarchical_id:
	TOK_ID {
		$$ = $1;
	} |
	hierarchical_id TOK_PACKAGESEP TOK_ID {
		if ($3->compare(0, 1, "\\") == 0)
			*$1 += "::" + $3->substr(1);
		else
			*$1 += "::" + *$3;
		delete $3;
		$$ = $1;
	} |
	hierarchical_id '.' TOK_ID {
		if ($3->compare(0, 1, "\\") == 0)
			*$1 += "." + $3->substr(1);
		else
			*$1 += "." + *$3;
		delete $3;
		$$ = $1;
	};
"""
def p_hierarchical_id(p):
	"""hierarchical_id : TOK_ID
	| hierarchical_id TOK_PACKAGESEP TOK_ID
	| hierarchical_id DOT TOK_ID
	"""
	p[0] = p[1:] if len(p) == 2 else p[1] + p[2:]
"""
hierarchical_type_id:
	TOK_USER_TYPE
	| TOK_PKG_USER_TYPE				// package qualified type name
	| '(' TOK_USER_TYPE ')'	{ $$ = $2; }		// non-standard grammar
	;

module:
	attr TOK_MODULE {
		enterTypeScope();
	} TOK_ID {
		do_not_require_port_stubs = false;
		AstNode *mod = new AstNode(AST_MODULE);
		ast_stack.back()->children.push_back(mod);
		ast_stack.push_back(mod);
		current_ast_mod = mod;
		port_stubs.clear();
		port_counter = 0;
		mod->str = *$4;
		append_attr(mod, $1);
		delete $4;
	} module_para_opt module_args_opt ';' module_body TOK_ENDMODULE {
		if (port_stubs.size() != 0)
			frontend_verilog_yyerror("Missing details for module port `%s'.",
					port_stubs.begin()->first.c_str());
		SET_AST_NODE_LOC(ast_stack.back(), @2, @$);
		ast_stack.pop_back();
		log_assert(ast_stack.size() == 1);
		current_ast_mod = NULL;
		exitTypeScope();
	};
"""
def p_module(p):
	"module : attr_STAR TOK_MODULE TOK_ID module_para_OPT module_args_OPT ';' module_body_STAR TOK_ENDMODULE"
	p[0] = p[2]


"""
module_para_opt:
	'#' '(' { astbuf1 = nullptr; } module_para_list { if (astbuf1) delete astbuf1; } ')' | /* empty */;
"""
def p_module_para(p):
	"""module_para : '#' '(' single_module_para_SEQ ')'
	"""
	p[0] = p[1]
	

"""
module_para_list:
	single_module_para | module_para_list ',' single_module_para;

single_module_para:
	/* empty */ |
	attr TOK_PARAMETER {
		if (astbuf1) delete astbuf1;
		astbuf1 = new AstNode(AST_PARAMETER);
		astbuf1->children.push_back(AstNode::mkconst_int(0, true));
		append_attr(astbuf1, $1);
	} param_type single_param_decl |
	attr TOK_LOCALPARAM {
		if (astbuf1) delete astbuf1;
		astbuf1 = new AstNode(AST_LOCALPARAM);
		astbuf1->children.push_back(AstNode::mkconst_int(0, true));
		append_attr(astbuf1, $1);
	} param_type single_param_decl |
	single_param_decl;
"""
def p_single_module_para(p):
	"""single_module_para :
	| attr_STAR TOK_PARAMETER param_type single_param_decl
	| attr_STAR TOK_LOCALPARAM param_type single_param_decl
	| single_param_decl
	"""
	p[0] = None
"""
module_args_opt:
	'(' ')' | /* empty */ | '(' module_args optional_comma ')';
"""
def p_module_args(p): ## LSEQ pour eviter un S/R
	"""module_args : '(' ')'
	| '(' module_arg_LSEQ ')'
	| '(' module_arg_LSEQ ',' ')'
	"""
	p[0] = None

"""
module_args:
	module_arg | module_args ',' module_arg;

optional_comma:
	',' | /* empty */;

module_arg_opt_assignment:
	'=' expr {
		if (ast_stack.back()->children.size() > 0 && ast_stack.back()->children.back()->type == AST_WIRE) {
			AstNode *wire = new AstNode(AST_IDENTIFIER);
			wire->str = ast_stack.back()->children.back()->str;
			if (ast_stack.back()->children.back()->is_input) {
				AstNode *n = ast_stack.back()->children.back();
				if (n->attributes.count(ID::defaultvalue))
					delete n->attributes.at(ID::defaultvalue);
				n->attributes[ID::defaultvalue] = $2;
			} else
			if (ast_stack.back()->children.back()->is_reg || ast_stack.back()->children.back()->is_logic)
				ast_stack.back()->children.push_back(new AstNode(AST_INITIAL, new AstNode(AST_BLOCK, new AstNode(AST_ASSIGN_LE, wire, $2))));
			else
				ast_stack.back()->children.push_back(new AstNode(AST_ASSIGN, wire, $2));
		} else
			frontend_verilog_yyerror("SystemVerilog interface in module port list cannot have a default value.");
	} |
	/* empty */;
"""
def p_module_arg_assignment(p):
	"""module_arg_assignment : '=' expr 
	"""
	p[0] = p[2]
"""
module_arg:
	TOK_ID {
		if (ast_stack.back()->children.size() > 0 && ast_stack.back()->children.back()->type == AST_WIRE) {
			AstNode *node = ast_stack.back()->children.back()->clone();
			node->str = *$1;
			node->port_id = ++port_counter;
			ast_stack.back()->children.push_back(node);
			SET_AST_NODE_LOC(node, @1, @1);
		} else {
			if (port_stubs.count(*$1) != 0)
				frontend_verilog_yyerror("Duplicate module port `%s'.", $1->c_str());
			port_stubs[*$1] = ++port_counter;
		}
		delete $1;
	} module_arg_opt_assignment |
	TOK_ID {
		astbuf1 = new AstNode(AST_INTERFACEPORT);
		astbuf1->children.push_back(new AstNode(AST_INTERFACEPORTTYPE));
		astbuf1->children[0]->str = *$1;
		delete $1;
	} TOK_ID {  /* SV interfaces */
		if (!sv_mode)
			frontend_verilog_yyerror("Interface found in port list (%s). This is not supported unless read_verilog is called with -sv!", $3->c_str());
		astbuf2 = astbuf1->clone(); // really only needed if multiple instances of same type.
		astbuf2->str = *$3;
		delete $3;
		astbuf2->port_id = ++port_counter;
		ast_stack.back()->children.push_back(astbuf2);
		delete astbuf1; // really only needed if multiple instances of same type.
	} module_arg_opt_assignment |
	attr wire_type range TOK_ID {
		AstNode *node = $2;
		node->str = *$4;
		SET_AST_NODE_LOC(node, @4, @4);
		node->port_id = ++port_counter;
		if ($3 != NULL)
			node->children.push_back($3);
		if (!node->is_input && !node->is_output)
			frontend_verilog_yyerror("Module port `%s' is neither input nor output.", $4->c_str());
		if (node->is_reg && node->is_input && !node->is_output && !sv_mode)
			frontend_verilog_yyerror("Input port `%s' is declared as register.", $4->c_str());
		ast_stack.back()->children.push_back(node);
		append_attr(node, $1);
		delete $4;
	} module_arg_opt_assignment |
	'.' '.' '.' {
		do_not_require_port_stubs = true;
	};
"""
def p_module_arg(p):
	"""module_arg : TOK_ID module_arg_assignment_OPT
	| TOK_ID TOK_ID module_arg_assignment_OPT
	| attr_STAR wire_type range_OPT TOK_ID module_arg_assignment_OPT
	"""
	p[0] = None

def p_module_arg_COMMA(p):
	"""module_arg_COMMA : module_arg ','
	"""
	p[0] = p[1]
"""
package:
	attr TOK_PACKAGE {
		enterTypeScope();
	} TOK_ID {
		AstNode *mod = new AstNode(AST_PACKAGE);
		ast_stack.back()->children.push_back(mod);
		ast_stack.push_back(mod);
		current_ast_mod = mod;
		mod->str = *$4;
		append_attr(mod, $1);
	} ';' package_body TOK_ENDPACKAGE {
		ast_stack.pop_back();
		current_ast_mod = NULL;
		exitTypeScope();
	};
"""
def p_package(p):
	"""package : attr_STAR TOK_PACKAGE TOK_ID ';' package_body_stmt_STAR TOK_ENDPACKAGE
	"""
	p[0] = None
"""
package_body:
	package_body package_body_stmt
	| // optional
	;

package_body_stmt:
	typedef_decl |
	localparam_decl |
	param_decl;
"""
def p_package_body_stmt(p):
	"""package_body_stmt : localparam_decl
	| param_decl
	"""
	p[0] = None
"""
interface:
	TOK_INTERFACE {
		enterTypeScope();
	} TOK_ID {
		do_not_require_port_stubs = false;
		AstNode *intf = new AstNode(AST_INTERFACE);
		ast_stack.back()->children.push_back(intf);
		ast_stack.push_back(intf);
		current_ast_mod = intf;
		port_stubs.clear();
		port_counter = 0;
		intf->str = *$3;
		delete $3;
	} module_para_opt module_args_opt ';' interface_body TOK_ENDINTERFACE {
		if (port_stubs.size() != 0)
			frontend_verilog_yyerror("Missing details for module port `%s'.",
				port_stubs.begin()->first.c_str());
		ast_stack.pop_back();
		log_assert(ast_stack.size() == 1);
		current_ast_mod = NULL;
		exitTypeScope();
	};
"""
def p_interface(p):
	"""interface : TOK_INTERFACE TOK_ID module_para_OPT module_args_OPT ';' interface_body_stmt_STAR TOK_ENDINTERFACE
	"""
	p[0] = None
"""
interface_body:
	interface_body interface_body_stmt |;

interface_body_stmt:
	param_decl | localparam_decl | typedef_decl | defparam_decl | wire_decl | always_stmt | assign_stmt |
	modport_stmt;
"""
def p_interface_body_stmt(p):
	"""interface_body_stmt : param_decl
	| localparam_decl
	| typedef_decl
	| defparam_decl
	| wire_decl
	| always_stmt
	| assign_stmt
	| modport_stmt
	"""
	p[0] = None
"""
non_opt_delay:
	'#' TOK_ID { delete $2; } |
	'#' TOK_CONSTVAL { delete $2; } |
	'#' TOK_REALVAL { delete $2; } |
	'#' '(' expr ')' { delete $3; } |
	'#' '(' expr ':' expr ':' expr ')' { delete $3; delete $5; delete $7; };

delay:
	non_opt_delay | /* empty */;
"""
def p_delay(p):
	"""delay : '#' TOK_ID
	| '#' TOK_CONSTVAL
	| '#' TOK_REALVAL
	| '#' '(' expr ')'
	| '#' '(' expr ':' expr ':' expr ')'
	"""
	p[0] = None
"""
wire_type:
	{
		astbuf3 = new AstNode(AST_WIRE);
		current_wire_rand = false;
		current_wire_const = false;
	} wire_type_token_list {
		$$ = astbuf3;
		SET_RULE_LOC(@$, @2, @$);
	};
"""
def p_wire_type(p):
	"""wire_type : wire_type_token_list
	"""
	p[0] = None

"""
wire_type_token_list:
	wire_type_token |
	wire_type_token_list wire_type_token |
	wire_type_token_io |
	hierarchical_type_id {
		astbuf3->is_custom_type = true;
		astbuf3->children.push_back(new AstNode(AST_WIRETYPE));
		astbuf3->children.back()->str = *$1;
	};
"""
def p_wire_type_token_list(p):
	"""wire_type_token_list : wire_type_token
	| wire_type_token_list wire_type_token
	| wire_type_token_io
	"""
	p[0] = None
"""
wire_type_token_io:
	TOK_INPUT {
		astbuf3->is_input = true;
	} |
	TOK_OUTPUT {
		astbuf3->is_output = true;
	} |
	TOK_INOUT {
		astbuf3->is_input = true;
		astbuf3->is_output = true;
	};
"""
def p_wire_type_token_io(p):
	"""wire_type_token_io : TOK_INPUT
	| TOK_OUTPUT
	| TOK_INOUT
	"""
	p[0] = p[1]
"""
wire_type_token:
	TOK_WIRE {
	} |
	TOK_WOR {
		astbuf3->is_wor = true;
	} |
	TOK_WAND {
		astbuf3->is_wand = true;
	} |
	TOK_REG {
		astbuf3->is_reg = true;
	} |
	TOK_LOGIC {
		astbuf3->is_logic = true;
	} |
	TOK_VAR {
		astbuf3->is_logic = true;
	} |
	TOK_INTEGER {
		astbuf3->is_reg = true;
		astbuf3->range_left = 31;
		astbuf3->range_right = 0;
		astbuf3->is_signed = true;
	} |
	TOK_GENVAR {
		astbuf3->type = AST_GENVAR;
		astbuf3->is_reg = true;
		astbuf3->is_signed = true;
		astbuf3->range_left = 31;
		astbuf3->range_right = 0;
	} |
	TOK_SIGNED {
		astbuf3->is_signed = true;
	} |
	TOK_RAND {
		current_wire_rand = true;
	} |
	TOK_CONST {
		current_wire_const = true;
	};
"""
def p_wire_type_token(p):
	"""wire_type_token : TOK_WIRE
	| TOK_WOR
	| TOK_WAND
	| TOK_REG
	| TOK_LOGIC
	| TOK_VAR
	| TOK_INTEGER
	| TOK_GENVAR
	| TOK_SIGNED
	| TOK_RAND
	| TOK_CONST
	"""
	p[0] = None
"""
non_opt_range:
	'[' expr ':' expr ']' {
		$$ = new AstNode(AST_RANGE);
		$$->children.push_back($2);
		$$->children.push_back($4);
	} |
	'[' expr TOK_POS_INDEXED expr ']' {
		$$ = new AstNode(AST_RANGE);
		AstNode *expr = new AstNode(AST_CONCAT, $2);
		$$->children.push_back(new AstNode(AST_SUB, new AstNode(AST_ADD, expr->clone(), $4), AstNode::mkconst_int(1, true)));
		$$->children.push_back(new AstNode(AST_ADD, expr, AstNode::mkconst_int(0, true)));
	} |
	'[' expr TOK_NEG_INDEXED expr ']' {
		$$ = new AstNode(AST_RANGE);
		AstNode *expr = new AstNode(AST_CONCAT, $2);
		$$->children.push_back(new AstNode(AST_ADD, expr, AstNode::mkconst_int(0, true)));
		$$->children.push_back(new AstNode(AST_SUB, new AstNode(AST_ADD, expr->clone(), AstNode::mkconst_int(1, true)), $4));
	} |
	'[' expr ']' {
		$$ = new AstNode(AST_RANGE);
		$$->children.push_back($2);
	};
"""
def p_range(p):
	"""range : '[' expr ':' expr ']'
	| '[' expr TOK_POS_INDEXED expr ']'
	| '[' expr TOK_NEG_INDEXED expr ']'
	| '[' expr ']'
	"""
	p[0] = None
"""
non_opt_multirange:
	non_opt_range non_opt_range {
		$$ = new AstNode(AST_MULTIRANGE, $1, $2);
	} |
	non_opt_multirange non_opt_range {
		$$ = $1;
		$$->children.push_back($2);
	};
"""
def p_multirange(p):
	"""multirange : range range range_STAR
	"""
	p[0] = None
"""
range:
	non_opt_range {
		$$ = $1;
	} |
	/* empty */ {
		$$ = NULL;
	};

range_or_multirange:
	range { $$ = $1; } |
	non_opt_multirange { $$ = $1; };

range_or_signed_int:
	range {
		$$ = $1;
	} |
	TOK_INTEGER {
		$$ = new AstNode(AST_RANGE);
		$$->children.push_back(AstNode::mkconst_int(31, true));
		$$->children.push_back(AstNode::mkconst_int(0, true));
		$$->is_signed = true;
	};

module_body:
	module_body module_body_stmt |
	/* the following line makes the generate..endgenrate keywords optional */
	module_body gen_stmt |
	/* empty */;
"""
def p_module_body(p):
	"""module_body : module_body_stmt
	| gen_stmt
	"""
	p[0] = None



"""

module_body_stmt:
	task_func_decl | specify_block | param_decl | localparam_decl | typedef_decl | defparam_decl | specparam_declaration | wire_decl | assign_stmt | cell_stmt |
	enum_decl |
	always_stmt | TOK_GENERATE module_gen_body TOK_ENDGENERATE | defattr | assert_property | checker_decl | ignored_specify_block;
"""
def p_module_body_stmt(p):
	"""module_body_stmt : always_stmt
	| assign_stmt
	| cell_stmt
	| defparam_decl
	| localparam_decl
	| param_decl
	| specify_block
	| specparam_declaration
	| task_func_decl
	| typedef_decl
	| wire_decl
	| TOK_GENERATE gen_stmt_or_module_body_stmt_STAR TOK_ENDGENERATE
	| IMPORT_DPI TOK_ID '(' ')' ';'
	| TOK_EVENT TOK_ID ';'
	"""
	p[0] = p[1]

"""
checker_decl:
	TOK_CHECKER TOK_ID ';' {
		AstNode *node = new AstNode(AST_GENBLOCK);
		node->str = *$2;
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
	} module_body TOK_ENDCHECKER {
		delete $2;
		ast_stack.pop_back();
	};

task_func_decl:
	attr TOK_DPI_FUNCTION TOK_ID TOK_ID {
		current_function_or_task = new AstNode(AST_DPI_FUNCTION, AstNode::mkconst_str(*$3), AstNode::mkconst_str(*$4));
		current_function_or_task->str = *$4;
		append_attr(current_function_or_task, $1);
		ast_stack.back()->children.push_back(current_function_or_task);
		delete $3;
		delete $4;
	} opt_dpi_function_args ';' {
		current_function_or_task = NULL;
	} |
	attr TOK_DPI_FUNCTION TOK_ID '=' TOK_ID TOK_ID {
		current_function_or_task = new AstNode(AST_DPI_FUNCTION, AstNode::mkconst_str(*$5), AstNode::mkconst_str(*$3));
		current_function_or_task->str = *$6;
		append_attr(current_function_or_task, $1);
		ast_stack.back()->children.push_back(current_function_or_task);
		delete $3;
		delete $5;
		delete $6;
	} opt_dpi_function_args ';' {
		current_function_or_task = NULL;
	} |
	attr TOK_DPI_FUNCTION TOK_ID ':' TOK_ID '=' TOK_ID TOK_ID {
		current_function_or_task = new AstNode(AST_DPI_FUNCTION, AstNode::mkconst_str(*$7), AstNode::mkconst_str(*$3 + ":" + RTLIL::unescape_id(*$5)));
		current_function_or_task->str = *$8;
		append_attr(current_function_or_task, $1);
		ast_stack.back()->children.push_back(current_function_or_task);
		delete $3;
		delete $5;
		delete $7;
		delete $8;
	} opt_dpi_function_args ';' {
		current_function_or_task = NULL;
	} |
	attr TOK_TASK opt_automatic TOK_ID {
		current_function_or_task = new AstNode(AST_TASK);
		current_function_or_task->str = *$4;
		append_attr(current_function_or_task, $1);
		ast_stack.back()->children.push_back(current_function_or_task);
		ast_stack.push_back(current_function_or_task);
		current_function_or_task_port_id = 1;
		delete $4;
	} task_func_args_opt ';' task_func_body TOK_ENDTASK {
		current_function_or_task = NULL;
		ast_stack.pop_back();
	} |
	attr TOK_FUNCTION opt_automatic opt_signed range_or_signed_int TOK_ID {
		current_function_or_task = new AstNode(AST_FUNCTION);
		current_function_or_task->str = *$6;
		append_attr(current_function_or_task, $1);
		ast_stack.back()->children.push_back(current_function_or_task);
		ast_stack.push_back(current_function_or_task);
		AstNode *outreg = new AstNode(AST_WIRE);
		outreg->str = *$6;
		outreg->is_signed = $4;
		outreg->is_reg = true;
		if ($5 != NULL) {
			outreg->children.push_back($5);
			outreg->is_signed = $4 || $5->is_signed;
			$5->is_signed = false;
		}
		current_function_or_task->children.push_back(outreg);
		current_function_or_task_port_id = 1;
		delete $6;
	} task_func_args_opt ';' task_func_body TOK_ENDFUNCTION {
		current_function_or_task = NULL;
		ast_stack.pop_back();
	};
"""
def p_task_func_decl(p):
	"""task_func_decl : attr_STAR TOK_TASK TOK_AUTOMATIC_OPT TOK_ID ';' behavioral_stmt_STAR TOK_ENDTASK
	| attr_STAR TOK_FUNCTION TOK_INTEGER TOK_ID ';' behavioral_stmt_STAR TOK_ENDFUNCTION
	| attr_STAR TOK_FUNCTION range_OPT TOK_ID ';' behavioral_stmt_STAR TOK_ENDFUNCTION
	"""
	p[0] = None
"""
dpi_function_arg:
	TOK_ID TOK_ID {
		current_function_or_task->children.push_back(AstNode::mkconst_str(*$1));
		delete $1;
		delete $2;
	} |
	TOK_ID {
		current_function_or_task->children.push_back(AstNode::mkconst_str(*$1));
		delete $1;
	};

opt_dpi_function_args:
	'(' dpi_function_args ')' |
	/* empty */;

dpi_function_args:
	dpi_function_args ',' dpi_function_arg |
	dpi_function_args ',' |
	dpi_function_arg |
	/* empty */;

opt_automatic:
	TOK_AUTOMATIC |
	/* empty */;

opt_signed:
	TOK_SIGNED {
		$$ = true;
	} |
	/* empty */ {
		$$ = false;
	};

task_func_args_opt:
	'(' ')' | /* empty */ | '(' {
		albuf = nullptr;
		astbuf1 = nullptr;
		astbuf2 = nullptr;
	} task_func_args optional_comma {
		delete astbuf1;
		if (astbuf2 != NULL)
			delete astbuf2;
		free_attr(albuf);
	} ')';

task_func_args:
	task_func_port | task_func_args ',' task_func_port;

task_func_port:
	attr wire_type range {
		if (albuf) {
			delete astbuf1;
			if (astbuf2 != NULL)
				delete astbuf2;
			free_attr(albuf);
		}
		albuf = $1;
		astbuf1 = $2;
		astbuf2 = $3;
		if (astbuf1->range_left >= 0 && astbuf1->range_right >= 0) {
			if (astbuf2) {
				frontend_verilog_yyerror("integer/genvar types cannot have packed dimensions (task/function arguments)");
			} else {
				astbuf2 = new AstNode(AST_RANGE);
				astbuf2->children.push_back(AstNode::mkconst_int(astbuf1->range_left, true));
				astbuf2->children.push_back(AstNode::mkconst_int(astbuf1->range_right, true));
			}
		}
		if (astbuf2 && astbuf2->children.size() != 2)
			frontend_verilog_yyerror("task/function argument range must be of the form: [<expr>:<expr>], [<expr>+:<expr>], or [<expr>-:<expr>]");
	} wire_name | wire_name;

task_func_body:
	task_func_body behavioral_stmt |
	/* empty */;

/*************************** specify parser ***************************/

specify_block:
	TOK_SPECIFY specify_item_list TOK_ENDSPECIFY;
"""
def p_specify_block(p):
	"""specify_block : TOK_SPECIFY specify_item_STAR TOK_ENDSPECIFY
	"""
	p[0] = None
"""
specify_item_list:
	specify_item specify_item_list |
	/* empty */;

specify_item:
	specify_if '(' specify_edge expr TOK_SPECIFY_OPER specify_target ')' '=' specify_rise_fall ';' {
		AstNode *en_expr = $1;
		char specify_edge = $3;
		AstNode *src_expr = $4;
		string *oper = $5;
		specify_target *target = $6;
		specify_rise_fall *timing = $9;

		if (specify_edge != 0 && target->dat == nullptr)
			frontend_verilog_yyerror("Found specify edge but no data spec.\n");

		AstNode *cell = new AstNode(AST_CELL);
		ast_stack.back()->children.push_back(cell);
		cell->str = stringf("$specify$%d", autoidx++);
		cell->children.push_back(new AstNode(AST_CELLTYPE));
		cell->children.back()->str = target->dat ? "$specify3" : "$specify2";

		char oper_polarity = 0;
		char oper_type = oper->at(0);

		if (oper->size() == 3) {
			oper_polarity = oper->at(0);
			oper_type = oper->at(1);
		}

		cell->children.push_back(new AstNode(AST_PARASET, AstNode::mkconst_int(oper_type == '*', false, 1)));
		cell->children.back()->str = "\\FULL";

		cell->children.push_back(new AstNode(AST_PARASET, AstNode::mkconst_int(oper_polarity != 0, false, 1)));
		cell->children.back()->str = "\\SRC_DST_PEN";

		cell->children.push_back(new AstNode(AST_PARASET, AstNode::mkconst_int(oper_polarity == '+', false, 1)));
		cell->children.back()->str = "\\SRC_DST_POL";

		cell->children.push_back(new AstNode(AST_PARASET, timing->rise.t_min));
		cell->children.back()->str = "\\T_RISE_MIN";

		cell->children.push_back(new AstNode(AST_PARASET, timing->rise.t_avg));
		cell->children.back()->str = "\\T_RISE_TYP";

		cell->children.push_back(new AstNode(AST_PARASET, timing->rise.t_max));
		cell->children.back()->str = "\\T_RISE_MAX";

		cell->children.push_back(new AstNode(AST_PARASET, timing->fall.t_min));
		cell->children.back()->str = "\\T_FALL_MIN";

		cell->children.push_back(new AstNode(AST_PARASET, timing->fall.t_avg));
		cell->children.back()->str = "\\T_FALL_TYP";

		cell->children.push_back(new AstNode(AST_PARASET, timing->fall.t_max));
		cell->children.back()->str = "\\T_FALL_MAX";

		cell->children.push_back(new AstNode(AST_ARGUMENT, en_expr ? en_expr : AstNode::mkconst_int(1, false, 1)));
		cell->children.back()->str = "\\EN";

		cell->children.push_back(new AstNode(AST_ARGUMENT, src_expr));
		cell->children.back()->str = "\\SRC";

		cell->children.push_back(new AstNode(AST_ARGUMENT, target->dst));
		cell->children.back()->str = "\\DST";

		if (target->dat)
		{
			cell->children.push_back(new AstNode(AST_PARASET, AstNode::mkconst_int(specify_edge != 0, false, 1)));
			cell->children.back()->str = "\\EDGE_EN";

			cell->children.push_back(new AstNode(AST_PARASET, AstNode::mkconst_int(specify_edge == 'p', false, 1)));
			cell->children.back()->str = "\\EDGE_POL";

			cell->children.push_back(new AstNode(AST_PARASET, AstNode::mkconst_int(target->polarity_op != 0, false, 1)));
			cell->children.back()->str = "\\DAT_DST_PEN";

			cell->children.push_back(new AstNode(AST_PARASET, AstNode::mkconst_int(target->polarity_op == '+', false, 1)));
			cell->children.back()->str = "\\DAT_DST_POL";

			cell->children.push_back(new AstNode(AST_ARGUMENT, target->dat));
			cell->children.back()->str = "\\DAT";
		}

		delete oper;
		delete target;
		delete timing;
	} |
	TOK_ID '(' specify_edge expr specify_condition ',' specify_edge expr specify_condition ',' specify_triple specify_opt_triple ')' ';' {
		if (*$1 != "$setup" && *$1 != "$hold" && *$1 != "$setuphold" && *$1 != "$removal" && *$1 != "$recovery" &&
				*$1 != "$recrem" && *$1 != "$skew" && *$1 != "$timeskew" && *$1 != "$fullskew" && *$1 != "$nochange")
			frontend_verilog_yyerror("Unsupported specify rule type: %s\n", $1->c_str());

		AstNode *src_pen = AstNode::mkconst_int($3 != 0, false, 1);
		AstNode *src_pol = AstNode::mkconst_int($3 == 'p', false, 1);
		AstNode *src_expr = $4, *src_en = $5 ? $5 : AstNode::mkconst_int(1, false, 1);

		AstNode *dst_pen = AstNode::mkconst_int($7 != 0, false, 1);
		AstNode *dst_pol = AstNode::mkconst_int($7 == 'p', false, 1);
		AstNode *dst_expr = $8, *dst_en = $9 ? $9 : AstNode::mkconst_int(1, false, 1);

		specify_triple *limit = $11;
		specify_triple *limit2 = $12;

		AstNode *cell = new AstNode(AST_CELL);
		ast_stack.back()->children.push_back(cell);
		cell->str = stringf("$specify$%d", autoidx++);
		cell->children.push_back(new AstNode(AST_CELLTYPE));
		cell->children.back()->str = "$specrule";

		cell->children.push_back(new AstNode(AST_PARASET, AstNode::mkconst_str(*$1)));
		cell->children.back()->str = "\\TYPE";

		cell->children.push_back(new AstNode(AST_PARASET, limit->t_min));
		cell->children.back()->str = "\\T_LIMIT_MIN";

		cell->children.push_back(new AstNode(AST_PARASET, limit->t_avg));
		cell->children.back()->str = "\\T_LIMIT_TYP";

		cell->children.push_back(new AstNode(AST_PARASET, limit->t_max));
		cell->children.back()->str = "\\T_LIMIT_MAX";

		cell->children.push_back(new AstNode(AST_PARASET, limit2 ? limit2->t_min : AstNode::mkconst_int(0, true)));
		cell->children.back()->str = "\\T_LIMIT2_MIN";

		cell->children.push_back(new AstNode(AST_PARASET, limit2 ? limit2->t_avg : AstNode::mkconst_int(0, true)));
		cell->children.back()->str = "\\T_LIMIT2_TYP";

		cell->children.push_back(new AstNode(AST_PARASET, limit2 ? limit2->t_max : AstNode::mkconst_int(0, true)));
		cell->children.back()->str = "\\T_LIMIT2_MAX";

		cell->children.push_back(new AstNode(AST_PARASET, src_pen));
		cell->children.back()->str = "\\SRC_PEN";

		cell->children.push_back(new AstNode(AST_PARASET, src_pol));
		cell->children.back()->str = "\\SRC_POL";

		cell->children.push_back(new AstNode(AST_PARASET, dst_pen));
		cell->children.back()->str = "\\DST_PEN";

		cell->children.push_back(new AstNode(AST_PARASET, dst_pol));
		cell->children.back()->str = "\\DST_POL";

		cell->children.push_back(new AstNode(AST_ARGUMENT, src_en));
		cell->children.back()->str = "\\SRC_EN";

		cell->children.push_back(new AstNode(AST_ARGUMENT, src_expr));
		cell->children.back()->str = "\\SRC";

		cell->children.push_back(new AstNode(AST_ARGUMENT, dst_en));
		cell->children.back()->str = "\\DST_EN";

		cell->children.push_back(new AstNode(AST_ARGUMENT, dst_expr));
		cell->children.back()->str = "\\DST";

		delete $1;
	};

specify_opt_triple:
	',' specify_triple {
		$$ = $2;
	} |
	/* empty */ {
		$$ = nullptr;
	};

specify_if:
	TOK_IF '(' expr ')' {
		$$ = $3;
	} |
	/* empty */ {
		$$ = nullptr;
	};

specify_condition:
	TOK_SPECIFY_AND expr {
		$$ = $2;
	} |
	/* empty */ {
		$$ = nullptr;
	};

specify_target:
	expr {
		$$ = new specify_target;
		$$->polarity_op = 0;
		$$->dst = $1;
		$$->dat = nullptr;
	} |
	'(' expr ':' expr ')'{
		$$ = new specify_target;
		$$->polarity_op = 0;
		$$->dst = $2;
		$$->dat = $4;
	} |
	'(' expr TOK_NEG_INDEXED expr ')'{
		$$ = new specify_target;
		$$->polarity_op = '-';
		$$->dst = $2;
		$$->dat = $4;
	} |
	'(' expr TOK_POS_INDEXED expr ')'{
		$$ = new specify_target;
		$$->polarity_op = '+';
		$$->dst = $2;
		$$->dat = $4;
	};

specify_edge:
	TOK_POSEDGE { $$ = 'p'; } |
	TOK_NEGEDGE { $$ = 'n'; } |
	{ $$ = 0; };

specify_rise_fall:
	specify_triple {
		$$ = new specify_rise_fall;
		$$->rise = *$1;
		$$->fall.t_min = $1->t_min->clone();
		$$->fall.t_avg = $1->t_avg->clone();
		$$->fall.t_max = $1->t_max->clone();
		delete $1;
	} |
	'(' specify_triple ',' specify_triple ')' {
		$$ = new specify_rise_fall;
		$$->rise = *$2;
		$$->fall = *$4;
		delete $2;
		delete $4;
	} |
	'(' specify_triple ',' specify_triple ',' specify_triple ')' {
		$$ = new specify_rise_fall;
		$$->rise = *$2;
		$$->fall = *$4;
		delete $2;
		delete $4;
        delete $6;
        log_file_warning(current_filename, get_line_num(), "Path delay expressions beyond rise/fall not currently supported. Ignoring.\n");
	} |
	'(' specify_triple ',' specify_triple ',' specify_triple ',' specify_triple ',' specify_triple ',' specify_triple ')' {
		$$ = new specify_rise_fall;
		$$->rise = *$2;
		$$->fall = *$4;
		delete $2;
		delete $4;
        delete $6;
        delete $8;
        delete $10;
        delete $12;
        log_file_warning(current_filename, get_line_num(), "Path delay expressions beyond rise/fall not currently supported. Ignoring.\n");
	} |
	'(' specify_triple ',' specify_triple ',' specify_triple ',' specify_triple ',' specify_triple ',' specify_triple ',' specify_triple ',' specify_triple ',' specify_triple ',' specify_triple ',' specify_triple ',' specify_triple ')' {
		$$ = new specify_rise_fall;
		$$->rise = *$2;
		$$->fall = *$4;
		delete $2;
		delete $4;
        delete $6;
        delete $8;
        delete $10;
        delete $12;
        delete $14;
        delete $16;
        delete $18;
        delete $20;
        delete $22;
        delete $24;
        log_file_warning(current_filename, get_line_num(), "Path delay expressions beyond rise/fall not currently supported. Ignoring.\n");
	}

specify_triple:
	expr {
		$$ = new specify_triple;
		$$->t_min = $1;
		$$->t_avg = $1->clone();
		$$->t_max = $1->clone();
	} |
	expr ':' expr ':' expr {
		$$ = new specify_triple;
		$$->t_min = $1;
		$$->t_avg = $3;
		$$->t_max = $5;
	};

/******************** ignored specify parser **************************/

ignored_specify_block:
	TOK_IGNORED_SPECIFY ignored_specify_item_opt TOK_ENDSPECIFY |
	TOK_IGNORED_SPECIFY TOK_ENDSPECIFY ;

ignored_specify_item_opt:
	ignored_specify_item_opt ignored_specify_item |
	ignored_specify_item ;

ignored_specify_item:
	specparam_declaration
	// | pulsestyle_declaration
	// | showcancelled_declaration
	| path_declaration
	| system_timing_declaration
	;

specparam_declaration:
	TOK_SPECPARAM list_of_specparam_assignments ';' |
	TOK_SPECPARAM specparam_range list_of_specparam_assignments ';' ;
"""
def p_specparam_declaration(p):
	"""specparam_declaration : TOK_SPECPARAM specparam_assignment_SEQ ';'
	"""
	p[0] = None
"""
// IEEE 1364-2005 calls this sinmply 'range' but the current 'range' rule allows empty match
// and the 'non_opt_range' rule allows index ranges not allowed by 1364-2005
// exxxxtending this for SV specparam would change this anyhow
specparam_range:
	'[' ignspec_constant_expression ':' ignspec_constant_expression ']' ;

list_of_specparam_assignments:
	specparam_assignment | list_of_specparam_assignments ',' specparam_assignment;

specparam_assignment:
	ignspec_id '=' ignspec_expr ;
"""
def p_specparam_assignment(p):
	"""specparam_assignment : TOK_ID '=' expr
	| '(' TOK_ID '=' '>' TOK_ID ')' '=' '(' expr ',' expr ')'
	"""
	p[0] = None
"""
ignspec_opt_cond:
	TOK_IF '(' ignspec_expr ')' | /* empty */;

path_declaration :
	simple_path_declaration ';'
	// | edge_sensitive_path_declaration
	// | state_dependent_path_declaration
	;

simple_path_declaration :
	ignspec_opt_cond parallel_path_description '=' path_delay_value |
	ignspec_opt_cond full_path_description '=' path_delay_value
	;

path_delay_value :
	'(' ignspec_expr list_of_path_delay_extra_expressions ')'
	|     ignspec_expr
	|     ignspec_expr list_of_path_delay_extra_expressions
	;

list_of_path_delay_extra_expressions :
	',' ignspec_expr
	| ',' ignspec_expr list_of_path_delay_extra_expressions
	;

specify_edge_identifier :
	TOK_POSEDGE | TOK_NEGEDGE ;

parallel_path_description :
	'(' specify_input_terminal_descriptor opt_polarity_operator '=' '>' specify_output_terminal_descriptor ')' |
	'(' specify_edge_identifier specify_input_terminal_descriptor '=' '>' '(' specify_output_terminal_descriptor opt_polarity_operator ':' ignspec_expr ')' ')' |
	'(' specify_edge_identifier specify_input_terminal_descriptor '=' '>' '(' specify_output_terminal_descriptor TOK_POS_INDEXED ignspec_expr ')' ')' ;

full_path_description :
	'(' list_of_path_inputs '*' '>' list_of_path_outputs ')' |
	'(' specify_edge_identifier list_of_path_inputs '*' '>' '(' list_of_path_outputs opt_polarity_operator ':' ignspec_expr ')' ')' |
	'(' specify_edge_identifier list_of_path_inputs '*' '>' '(' list_of_path_outputs TOK_POS_INDEXED ignspec_expr ')' ')' ;

// This was broken into 2 rules to solve shift/reduce conflicts
list_of_path_inputs :
	specify_input_terminal_descriptor                  opt_polarity_operator  |
	specify_input_terminal_descriptor more_path_inputs opt_polarity_operator ;

more_path_inputs :
    ',' specify_input_terminal_descriptor |
    more_path_inputs ',' specify_input_terminal_descriptor ;

list_of_path_outputs :
	specify_output_terminal_descriptor |
	list_of_path_outputs ',' specify_output_terminal_descriptor ;

opt_polarity_operator :
	'+'
	| '-'
	| ;

// Good enough for the time being
specify_input_terminal_descriptor :
	ignspec_id ;

// Good enough for the time being
specify_output_terminal_descriptor :
	ignspec_id ;

system_timing_declaration :
	ignspec_id '(' system_timing_args ')' ';' ;

system_timing_arg :
	TOK_POSEDGE ignspec_id |
	TOK_NEGEDGE ignspec_id |
	ignspec_expr ;

system_timing_args :
	system_timing_arg |
	system_timing_args TOK_IGNORED_SPECIFY_AND system_timing_arg |
	system_timing_args ',' system_timing_arg ;

// for the time being this is OK, but we may write our own expr here.
// as I'm not sure it is legal to use a full expr here (probably not)
// On the other hand, other rules requiring constant expressions also use 'expr'
// (such as param assignment), so we may leave this as-is, perhaps adding runtime checks for constant-ness
ignspec_constant_expression:
	expr { delete $1; };

ignspec_expr:
	expr { delete $1; } |
	expr ':' expr ':' expr {
		delete $1;
		delete $3;
		delete $5;
	};

ignspec_id:
	TOK_ID { delete $1; }
	range_or_multirange { delete $3; };

/**********************************************************************/

param_signed:
	TOK_SIGNED {
		astbuf1->is_signed = true;
	} | /* empty */;

param_integer:
	TOK_INTEGER {
		if (astbuf1->children.size() != 1)
			frontend_verilog_yyerror("Internal error in param_integer - should not happen?");
		astbuf1->children.push_back(new AstNode(AST_RANGE));
		astbuf1->children.back()->children.push_back(AstNode::mkconst_int(31, true));
		astbuf1->children.back()->children.push_back(AstNode::mkconst_int(0, true));
		astbuf1->is_signed = true;
	} | /* empty */;

param_real:
	TOK_REAL {
		if (astbuf1->children.size() != 1)
			frontend_verilog_yyerror("Parameter already declared as integer, cannot set to real.");
		astbuf1->children.push_back(new AstNode(AST_REALVALUE));
	} | /* empty */;

param_range:
	range {
		if ($1 != NULL) {
			if (astbuf1->children.size() != 1)
				frontend_verilog_yyerror("integer/real parameters should not have a range.");
			astbuf1->children.push_back($1);
		}
	};

param_type:
	param_signed param_integer param_real param_range |
	hierarchical_type_id {
		astbuf1->is_custom_type = true;
		astbuf1->children.push_back(new AstNode(AST_WIRETYPE));
		astbuf1->children.back()->str = *$1;
	};
"""
def p_param_type(p):
	"""param_type : TOK_SIGNED_OPT TOK_INTEGER_OPT TOK_REAL_OPT range_OPT
	"""
	p[0] = None
"""
param_decl:
	attr TOK_PARAMETER {
		astbuf1 = new AstNode(AST_PARAMETER);
		astbuf1->children.push_back(AstNode::mkconst_int(0, true));
		append_attr(astbuf1, $1);
	} param_type param_decl_list ';' {
		delete astbuf1;
	};
"""
def p_param_decl(p):
	"""param_decl : attr_STAR TOK_PARAMETER param_type single_param_decl_SEQ ';'
	"""
	p[0] = None
"""
localparam_decl:
	attr TOK_LOCALPARAM {
		astbuf1 = new AstNode(AST_LOCALPARAM);
		astbuf1->children.push_back(AstNode::mkconst_int(0, true));
		append_attr(astbuf1, $1);
	} param_type param_decl_list ';' {
		delete astbuf1;
	};
"""
def p_localparam_decl(p):
	"""localparam_decl : attr_STAR TOK_LOCALPARAM param_type single_param_decl_SEQ ';'
	"""
	p[0] = None
"""
param_decl_list:
	single_param_decl | param_decl_list ',' single_param_decl;

single_param_decl:
	TOK_ID '=' expr {
		AstNode *node;
		if (astbuf1 == nullptr) {
			if (!sv_mode)
				frontend_verilog_yyerror("In pure Verilog (not SystemVerilog), parameter/localparam with an initializer must use the parameter/localparam keyword");
			node = new AstNode(AST_PARAMETER);
			node->children.push_back(AstNode::mkconst_int(0, true));
		} else {
			node = astbuf1->clone();
		}
		node->str = *$1;
		delete node->children[0];
		node->children[0] = $3;
		ast_stack.back()->children.push_back(node);
		delete $1;
	};
"""
def p_single_param_decl(p):
	"""single_param_decl : TOK_ID '=' expr
	"""
	p[0] = None
"""
defparam_decl:
	TOK_DEFPARAM defparam_decl_list ';';
"""
def p_defparam_decl(p):
	"""defparam_decl : TOK_DEFPARAM single_defparam_decl_SEQ ';'
	"""
	p[0] = None
"""
defparam_decl_list:
	single_defparam_decl | defparam_decl_list ',' single_defparam_decl;

single_defparam_decl:
	range rvalue '=' expr {
		AstNode *node = new AstNode(AST_DEFPARAM);
		node->children.push_back($2);
		node->children.push_back($4);
		if ($1 != NULL)
			node->children.push_back($1);
		ast_stack.back()->children.push_back(node);
	};
"""
def p_single_defparam_decl(p):
	"""single_defparam_decl : range_OPT rvalue '=' expr
	"""
	p[0] = None
"""
enum_type: TOK_ENUM {
		static int enum_count;
		// create parent node for the enum
		astbuf2 = new AstNode(AST_ENUM);
		ast_stack.back()->children.push_back(astbuf2);
		astbuf2->str = std::string("$enum");
		astbuf2->str += std::to_string(enum_count++);
		// create the template for the names
		astbuf1 = new AstNode(AST_ENUM_ITEM);
		astbuf1->children.push_back(AstNode::mkconst_int(0, true));
	 } param_signed enum_base_type '{' enum_name_list '}' {  // create template for the enum vars
								auto tnode = astbuf1->clone();
								delete astbuf1;
								astbuf1 = tnode;
								tnode->type = AST_WIRE;
								tnode->attributes["\\enum_type"] = AstNode::mkconst_str(astbuf2->str);
								// drop constant but keep any range
								delete tnode->children[0];
								tnode->children.erase(tnode->children.begin()); }
	 ;
"""
def p_enum_type(p):
	"""enum_type : TOK_ENUM '{' enum_name_decl_SEQ '}'
	"""
	p[0] = None
"""
enum_base_type: int_vec param_range
	| int_atom
	| /* nothing */		{astbuf1->is_reg = true; addRange(astbuf1); }
	;

int_atom: TOK_INTEGER		{astbuf1->is_reg=true; addRange(astbuf1); }		// probably should do byte, range [7:0] here
	;

int_vec: TOK_REG {astbuf1->is_reg = true;}
	| TOK_LOGIC  {astbuf1->is_logic = true;}
	;

enum_name_list:
	enum_name_decl
	| enum_name_list ',' enum_name_decl
	;

enum_name_decl:
	TOK_ID opt_enum_init {
		// put in fn
		log_assert(astbuf1);
		log_assert(astbuf2);
		auto node = astbuf1->clone();
		node->str = *$1;
		delete $1;
		delete node->children[0];
		node->children[0] = $2 ?: new AstNode(AST_NONE);
		astbuf2->children.push_back(node);
	}
	;
"""
def p_enum_name_decl(p):
	"""enum_name_decl : TOK_ID
	"""
	p[0] = None
"""
opt_enum_init:
	'=' basic_expr		{ $$ = $2; }	// TODO: restrict this
	| /* optional */	{ $$ = NULL; }
	;

enum_var_list:
	enum_var
	| enum_var_list ',' enum_var
	;

enum_var: TOK_ID {
		log_assert(astbuf1);
		log_assert(astbuf2);
		auto node = astbuf1->clone();
		ast_stack.back()->children.push_back(node);
		node->str = *$1;
		delete $1;
		node->is_enum = true;
	}
	;

enum_decl: enum_type enum_var_list ';'			{
		//enum_type creates astbuf1 for use by typedef only
		delete astbuf1;
	}
	;

wire_decl:
	attr wire_type range {
		albuf = $1;
		astbuf1 = $2;
		astbuf2 = $3;
		if (astbuf1->range_left >= 0 && astbuf1->range_right >= 0) {
			if (astbuf2) {
				frontend_verilog_yyerror("integer/genvar types cannot have packed dimensions.");
			} else {
				astbuf2 = new AstNode(AST_RANGE);
				astbuf2->children.push_back(AstNode::mkconst_int(astbuf1->range_left, true));
				astbuf2->children.push_back(AstNode::mkconst_int(astbuf1->range_right, true));
			}
		}
		if (astbuf2 && astbuf2->children.size() != 2)
			frontend_verilog_yyerror("wire/reg/logic packed dimension must be of the form: [<expr>:<expr>], [<expr>+:<expr>], or [<expr>-:<expr>]");
	} delay wire_name_list {
		delete astbuf1;
		if (astbuf2 != NULL)
			delete astbuf2;
		free_attr(albuf);
	} ';' |
	attr TOK_SUPPLY0 TOK_ID {
		ast_stack.back()->children.push_back(new AstNode(AST_WIRE));
		ast_stack.back()->children.back()->str = *$3;
		append_attr(ast_stack.back()->children.back(), $1);
		ast_stack.back()->children.push_back(new AstNode(AST_ASSIGN, new AstNode(AST_IDENTIFIER), AstNode::mkconst_int(0, false, 1)));
		ast_stack.back()->children.back()->children[0]->str = *$3;
		delete $3;
	} opt_supply_wires ';' |
	attr TOK_SUPPLY1 TOK_ID {
		ast_stack.back()->children.push_back(new AstNode(AST_WIRE));
		ast_stack.back()->children.back()->str = *$3;
		append_attr(ast_stack.back()->children.back(), $1);
		ast_stack.back()->children.push_back(new AstNode(AST_ASSIGN, new AstNode(AST_IDENTIFIER), AstNode::mkconst_int(1, false, 1)));
		ast_stack.back()->children.back()->children[0]->str = *$3;
		delete $3;
	} opt_supply_wires ';';
"""
def p_wire_decl(p):
	"""wire_decl : attr_STAR wire_type range_OPT delay_OPT wire_name_and_opt_assign_SEQ ';'
	| attr_STAR TOK_SUPPLY0 TOK_ID_SEQ ';'
	| attr_STAR TOK_SUPPLY1 TOK_ID_SEQ ';'
	"""
	p[0] = None
	
"""
opt_supply_wires:
	/* empty */ |
	opt_supply_wires ',' TOK_ID {
		AstNode *wire_node = ast_stack.back()->children.at(GetSize(ast_stack.back()->children)-2)->clone();
		AstNode *assign_node = ast_stack.back()->children.at(GetSize(ast_stack.back()->children)-1)->clone();
		wire_node->str = *$3;
		assign_node->children[0]->str = *$3;
		ast_stack.back()->children.push_back(wire_node);
		ast_stack.back()->children.push_back(assign_node);
		delete $3;
	};

wire_name_list:
	wire_name_and_opt_assign | wire_name_list ',' wire_name_and_opt_assign;

wire_name_and_opt_assign:
	wire_name {
		bool attr_anyconst = false;
		bool attr_anyseq = false;
		bool attr_allconst = false;
		bool attr_allseq = false;
		if (ast_stack.back()->children.back()->get_bool_attribute(ID::anyconst)) {
			delete ast_stack.back()->children.back()->attributes.at(ID::anyconst);
			ast_stack.back()->children.back()->attributes.erase(ID::anyconst);
			attr_anyconst = true;
		}
		if (ast_stack.back()->children.back()->get_bool_attribute(ID::anyseq)) {
			delete ast_stack.back()->children.back()->attributes.at(ID::anyseq);
			ast_stack.back()->children.back()->attributes.erase(ID::anyseq);
			attr_anyseq = true;
		}
		if (ast_stack.back()->children.back()->get_bool_attribute(ID::allconst)) {
			delete ast_stack.back()->children.back()->attributes.at(ID::allconst);
			ast_stack.back()->children.back()->attributes.erase(ID::allconst);
			attr_allconst = true;
		}
		if (ast_stack.back()->children.back()->get_bool_attribute(ID::allseq)) {
			delete ast_stack.back()->children.back()->attributes.at(ID::allseq);
			ast_stack.back()->children.back()->attributes.erase(ID::allseq);
			attr_allseq = true;
		}
		if (current_wire_rand || attr_anyconst || attr_anyseq || attr_allconst || attr_allseq) {
			AstNode *wire = new AstNode(AST_IDENTIFIER);
			AstNode *fcall = new AstNode(AST_FCALL);
			wire->str = ast_stack.back()->children.back()->str;
			fcall->str = current_wire_const ? "\\$anyconst" : "\\$anyseq";
			if (attr_anyconst)
				fcall->str = "\\$anyconst";
			if (attr_anyseq)
				fcall->str = "\\$anyseq";
			if (attr_allconst)
				fcall->str = "\\$allconst";
			if (attr_allseq)
				fcall->str = "\\$allseq";
			fcall->attributes[ID::reg] = AstNode::mkconst_str(RTLIL::unescape_id(wire->str));
			ast_stack.back()->children.push_back(new AstNode(AST_ASSIGN, wire, fcall));
		}
	} |
	wire_name '=' expr {
		AstNode *wire = new AstNode(AST_IDENTIFIER);
		wire->str = ast_stack.back()->children.back()->str;
		if (astbuf1->is_input) {
			if (astbuf1->attributes.count(ID::defaultvalue))
				delete astbuf1->attributes.at(ID::defaultvalue);
			astbuf1->attributes[ID::defaultvalue] = $3;
		}
		else if (astbuf1->is_reg || astbuf1->is_logic){
			AstNode *assign = new AstNode(AST_ASSIGN_LE, wire, $3);
			AstNode *block = new AstNode(AST_BLOCK, assign);
			AstNode *init = new AstNode(AST_INITIAL, block);

			SET_AST_NODE_LOC(assign, @1, @3);
			SET_AST_NODE_LOC(block, @1, @3);
			SET_AST_NODE_LOC(init, @1, @3);

			ast_stack.back()->children.push_back(init);
		}
		else {
			AstNode *assign = new AstNode(AST_ASSIGN, wire, $3);
			SET_AST_NODE_LOC(assign, @1, @3);
			ast_stack.back()->children.push_back(assign);
		}

	};
"""
def p_wire_name_and_opt_assign(p):
	"""wire_name_and_opt_assign : wire_name
	| wire_name '=' expr
	"""
	p[0] = None
"""
wire_name:
	TOK_ID range_or_multirange {
		if (astbuf1 == nullptr)
			frontend_verilog_yyerror("Internal error - should not happen - no AST_WIRE node.");
		AstNode *node = astbuf1->clone();
		node->str = *$1;
		append_attr_clone(node, albuf);
		if (astbuf2 != NULL)
			node->children.push_back(astbuf2->clone());
		if ($2 != NULL) {
			if (node->is_input || node->is_output)
				frontend_verilog_yyerror("input/output/inout ports cannot have unpacked dimensions.");
			if (!astbuf2 && !node->is_custom_type) {
				AstNode *rng = new AstNode(AST_RANGE);
				rng->children.push_back(AstNode::mkconst_int(0, true));
				rng->children.push_back(AstNode::mkconst_int(0, true));
				node->children.push_back(rng);
			}
			node->type = AST_MEMORY;
			auto *rangeNode = $2;
			if (rangeNode->type == AST_RANGE && rangeNode->children.size() == 1) {
				// SV array size [n], rewrite as [n-1:0]
				rangeNode->children[0] = new AstNode(AST_SUB, rangeNode->children[0], AstNode::mkconst_int(1, true));
				rangeNode->children.push_back(AstNode::mkconst_int(0, false));
			}
			node->children.push_back(rangeNode);
		}
		if (current_function_or_task == NULL) {
			if (do_not_require_port_stubs && (node->is_input || node->is_output) && port_stubs.count(*$1) == 0) {
				port_stubs[*$1] = ++port_counter;
			}
			if (port_stubs.count(*$1) != 0) {
				if (!node->is_input && !node->is_output)
					frontend_verilog_yyerror("Module port `%s' is neither input nor output.", $1->c_str());
				if (node->is_reg && node->is_input && !node->is_output && !sv_mode)
					frontend_verilog_yyerror("Input port `%s' is declared as register.", $1->c_str());
				node->port_id = port_stubs[*$1];
				port_stubs.erase(*$1);
			} else {
				if (node->is_input || node->is_output)
					frontend_verilog_yyerror("Module port `%s' is not declared in module header.", $1->c_str());
			}
		} else {
			if (node->is_input || node->is_output)
				node->port_id = current_function_or_task_port_id++;
		}
		//FIXME: for some reason, TOK_ID has a location which always points to one column *after* the real last column...
		SET_AST_NODE_LOC(node, @1, @1);
		ast_stack.back()->children.push_back(node);

		delete $1;
	};
"""
def p_wire_name(p):
	"""wire_name : TOK_ID range_STAR
	"""
	p[0] = None
"""
assign_stmt:
	TOK_ASSIGN delay assign_expr_list ';';
"""
def p_assign_stmt(p):
	"""assign_stmt : TOK_ASSIGN delay_OPT assign_expr_SEQ ';'
	"""
	p[0] = None
"""
assign_expr_list:
	assign_expr | assign_expr_list ',' assign_expr;

assign_expr:
	lvalue '=' expr {
		AstNode *node = new AstNode(AST_ASSIGN, $1, $3);
		SET_AST_NODE_LOC(node, @$, @$);
		ast_stack.back()->children.push_back(node);
	};
"""
def p_assign_expr(p):
	"""assign_expr : lvalue '=' expr
	"""
	p[0] = None
"""
type_name: TOK_ID		// first time seen
	 | TOK_USER_TYPE	{ if (isInLocalScope($1)) frontend_verilog_yyerror("Duplicate declaration of TYPEDEF '%s'", $1->c_str()+1); }
	 ;
"""
def p_type_name(p):
	"""type_name : TOK_ID
	| TOK_USER_TYPE
	"""
	p[0] = p[1]
"""
typedef_decl:
	TOK_TYPEDEF wire_type range type_name range_or_multirange ';' {
		astbuf1 = $2;
		astbuf2 = $3;
		if (astbuf1->range_left >= 0 && astbuf1->range_right >= 0) {
			if (astbuf2) {
				frontend_verilog_yyerror("integer/genvar types cannot have packed dimensions.");
			} else {
				astbuf2 = new AstNode(AST_RANGE);
				astbuf2->children.push_back(AstNode::mkconst_int(astbuf1->range_left, true));
				astbuf2->children.push_back(AstNode::mkconst_int(astbuf1->range_right, true));
			}
		}
		if (astbuf2 && astbuf2->children.size() != 2)
			frontend_verilog_yyerror("wire/reg/logic packed dimension must be of the form: [<expr>:<expr>], [<expr>+:<expr>], or [<expr>-:<expr>]");
		if (astbuf2)
			astbuf1->children.push_back(astbuf2);

		if ($5 != NULL) {
			if (!astbuf2) {
				AstNode *rng = new AstNode(AST_RANGE);
				rng->children.push_back(AstNode::mkconst_int(0, true));
				rng->children.push_back(AstNode::mkconst_int(0, true));
				astbuf1->children.push_back(rng);
			}
			astbuf1->type = AST_MEMORY;
			auto *rangeNode = $5;
			if (rangeNode->type == AST_RANGE && rangeNode->children.size() == 1) {
				// SV array size [n], rewrite as [n-1:0]
				rangeNode->children[0] = new AstNode(AST_SUB, rangeNode->children[0], AstNode::mkconst_int(1, true));
				rangeNode->children.push_back(AstNode::mkconst_int(0, false));
			}
			astbuf1->children.push_back(rangeNode);
		}
		addTypedefNode($4, astbuf1);
	} |
	TOK_TYPEDEF enum_type type_name ';' {
		addTypedefNode($3, astbuf1);
	}
	;
"""
def p_typedef_decl(p):
	"""typedef_decl : TOK_TYPEDEF wire_type range_OPT type_name range_STAR ';'
	| TOK_TYPEDEF enum_type type_name ';'
	"""
	p[0] = None
"""
cell_stmt:
	attr TOK_ID {
		astbuf1 = new AstNode(AST_CELL);
		append_attr(astbuf1, $1);
		astbuf1->children.push_back(new AstNode(AST_CELLTYPE));
		astbuf1->children[0]->str = *$2;
		delete $2;
	} cell_parameter_list_opt cell_list ';' {
		delete astbuf1;
	} |
	attr tok_prim_wrapper delay {
		astbuf1 = new AstNode(AST_PRIMITIVE);
		astbuf1->str = *$2;
		append_attr(astbuf1, $1);
		delete $2;
	} prim_list ';' {
		delete astbuf1;
	};
"""
def p_cell_stmt(p):
	"""cell_stmt : attr_STAR TOK_ID cell_parameter_list_OPT single_cell_SEQ ';'
	| attr_STAR TOK_PRIMITIVE delay_OPT single_prim_SEQ ';'
	| attr_STAR TOK_OR delay_OPT single_prim_SEQ ';'
	"""
	p[0] = None
"""
tok_prim_wrapper:
	TOK_PRIMITIVE {
		$$ = $1;
	} |
	TOK_OR {
		$$ = new std::string("or");
	};

cell_list:
	single_cell |
	cell_list ',' single_cell;

single_cell:
	TOK_ID {
		astbuf2 = astbuf1->clone();
		if (astbuf2->type != AST_PRIMITIVE)
			astbuf2->str = *$1;
		delete $1;
		ast_stack.back()->children.push_back(astbuf2);
	} '(' cell_port_list ')' {
		SET_AST_NODE_LOC(astbuf2, @1, @$);
	} |
	TOK_ID non_opt_range {
		astbuf2 = astbuf1->clone();
		if (astbuf2->type != AST_PRIMITIVE)
			astbuf2->str = *$1;
		delete $1;
		ast_stack.back()->children.push_back(new AstNode(AST_CELLARRAY, $2, astbuf2));
	} '(' cell_port_list ')'{
		SET_AST_NODE_LOC(astbuf2, @1, @$);
	};
"""
def p_single_cell(p):
	"""single_cell : TOK_ID '(' cell_port_SEQ ')'
	"""
	
"""
prim_list:
	single_prim |
	prim_list ',' single_prim;

single_prim:
	single_cell |
	/* no name */ {
		astbuf2 = astbuf1->clone();
		ast_stack.back()->children.push_back(astbuf2);
	} '(' cell_port_list ')';
"""
def p_single_prim(p):
	"""single_prim : single_cell
	| '(' cell_port_SEQ ')'
	"""
	p[0] = None
"""
cell_parameter_list_opt:
	'#' '(' cell_parameter_list ')' | /* empty */;
"""
def p_cell_parameter_list(p):
	"""cell_parameter_list : '#' '(' cell_parameter_SEQ ')'
	"""
	p[0] = None
"""
cell_parameter_list:
	cell_parameter | cell_parameter_list ',' cell_parameter;

cell_parameter:
	/* empty */ |
	expr {
		AstNode *node = new AstNode(AST_PARASET);
		astbuf1->children.push_back(node);
		node->children.push_back($1);
	} |
	'.' TOK_ID '(' expr ')' {
		AstNode *node = new AstNode(AST_PARASET);
		node->str = *$2;
		astbuf1->children.push_back(node);
		node->children.push_back($4);
		delete $2;
	};
"""
def p_cell_parameter(p):
	"""cell_parameter :
	| expr
	| DOT TOK_ID '(' expr ')'
	"""
	p[0] = None
"""
cell_port_list:
	cell_port_list_rules {
		// remove empty args from end of list
		while (!astbuf2->children.empty()) {
			AstNode *node = astbuf2->children.back();
			if (node->type != AST_ARGUMENT) break;
			if (!node->children.empty()) break;
			if (!node->str.empty()) break;
			astbuf2->children.pop_back();
			delete node;
		}

		// check port types
		bool has_positional_args = false;
		bool has_named_args = false;
		for (auto node : astbuf2->children) {
			if (node->type != AST_ARGUMENT) continue;
			if (node->str.empty())
				has_positional_args = true;
			else
				has_named_args = true;
		}

		if (has_positional_args && has_named_args)
			frontend_verilog_yyerror("Mix of positional and named cell ports.");
	};

cell_port_list_rules:
	cell_port | cell_port_list_rules ',' cell_port;

cell_port:
	attr {
		AstNode *node = new AstNode(AST_ARGUMENT);
		astbuf2->children.push_back(node);
		free_attr($1);
	} |
	attr expr {
		AstNode *node = new AstNode(AST_ARGUMENT);
		astbuf2->children.push_back(node);
		node->children.push_back($2);
		free_attr($1);
	} |
	attr '.' TOK_ID '(' expr ')' {
		AstNode *node = new AstNode(AST_ARGUMENT);
		node->str = *$3;
		astbuf2->children.push_back(node);
		node->children.push_back($5);
		delete $3;
		free_attr($1);
	} |
	attr '.' TOK_ID '(' ')' {
		AstNode *node = new AstNode(AST_ARGUMENT);
		node->str = *$3;
		astbuf2->children.push_back(node);
		delete $3;
		free_attr($1);
	} |
	attr '.' TOK_ID {
		AstNode *node = new AstNode(AST_ARGUMENT);
		node->str = *$3;
		astbuf2->children.push_back(node);
		node->children.push_back(new AstNode(AST_IDENTIFIER));
		node->children.back()->str = *$3;
		delete $3;
		free_attr($1);
	} |
	attr TOK_WILDCARD_CONNECT {
		if (!sv_mode)
			frontend_verilog_yyerror("Wildcard port connections are only supported in SystemVerilog mode.");
		astbuf2->attributes[ID::wildcard_port_conns] = AstNode::mkconst_int(1, false);
	};
"""
def p_cell_port(p):
	"""cell_port : attr_STAR
	| attr_STAR expr
	| attr_STAR DOT TOK_ID '(' expr ')' 
	"""
	p[0] = None
"""
always_comb_or_latch:
	TOK_ALWAYS_COMB {
		$$ = false;
	} |
	TOK_ALWAYS_LATCH {
		$$ = true;
	};
"""
def p_always_comb_or_latch(p):
	"""always_comb_or_latch : TOK_ALWAYS_COMB
	| TOK_ALWAYS_LATCH
	"""
	p[0] = p[1]
"""
always_or_always_ff:
	TOK_ALWAYS {
		$$ = false;
	} |
	TOK_ALWAYS_FF {
		$$ = true;
	};
"""
def p_always_or_always_ff(p): ### forever : ajout ?
	"""always_or_always_ff : TOK_ALWAYS
	| TOK_ALWAYS_FF
	"""
	p[0] = p[1]
"""
always_stmt:
	attr always_or_always_ff {
		AstNode *node = new AstNode(AST_ALWAYS);
		append_attr(node, $1);
		if ($2)
			node->attributes[ID::always_ff] = AstNode::mkconst_int(1, false);
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
	} always_cond {
		AstNode *block = new AstNode(AST_BLOCK);
		ast_stack.back()->children.push_back(block);
		ast_stack.push_back(block);
	} behavioral_stmt {
		SET_AST_NODE_LOC(ast_stack.back(), @6, @6);
		ast_stack.pop_back();

		SET_AST_NODE_LOC(ast_stack.back(), @2, @$);
		ast_stack.pop_back();

		SET_RULE_LOC(@$, @2, @$);
	} |
	attr always_comb_or_latch {
		AstNode *node = new AstNode(AST_ALWAYS);
		append_attr(node, $1);
		if ($2)
			node->attributes[ID::always_latch] = AstNode::mkconst_int(1, false);
		else
			node->attributes[ID::always_comb] = AstNode::mkconst_int(1, false);
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
		AstNode *block = new AstNode(AST_BLOCK);
		ast_stack.back()->children.push_back(block);
		ast_stack.push_back(block);
	} behavioral_stmt {
		ast_stack.pop_back();
		ast_stack.pop_back();
	} |
	attr TOK_INITIAL {
		AstNode *node = new AstNode(AST_INITIAL);
		append_attr(node, $1);
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
		AstNode *block = new AstNode(AST_BLOCK);
		ast_stack.back()->children.push_back(block);
		ast_stack.push_back(block);
	} behavioral_stmt {
		ast_stack.pop_back();
		ast_stack.pop_back();
	};
"""
def p_always_stmt(p):
	"""always_stmt : attr_STAR always_or_always_ff always_cond behavioral_stmt
	| attr_STAR always_comb_or_latch behavioral_stmt
	| attr_STAR TOK_INITIAL behavioral_stmt
	"""
	p[0] = None
"""
always_cond:
	'@' '(' always_events ')' |
	'@' '(' '*' ')' |
	'@' ATTR_BEGIN ')' |
	'@' '(' ATTR_END |
	'@' '*' |
	/* empty */;
"""
def p_always_cond(p):
	"""always_cond : '@' '(' always_events ')'
	| '@' '(' '*' ')'
	| '@' ATTR_BEGIN ')'
	| '@' '(' ATTR_END
	| '@' '*'
	|
	"""
	p[0] = None
"""
always_events:
	always_event |
	always_events TOK_OR always_event |
	always_events ',' always_event;
"""
def p_always_events(p):
	"""always_events : always_event
	| always_events TOK_OR always_event
	| always_events ',' always_event
	"""
	p[0] = None
"""
always_event:
	TOK_POSEDGE expr {
		AstNode *node = new AstNode(AST_POSEDGE);
		ast_stack.back()->children.push_back(node);
		node->children.push_back($2);
	} |
	TOK_NEGEDGE expr {
		AstNode *node = new AstNode(AST_NEGEDGE);
		ast_stack.back()->children.push_back(node);
		node->children.push_back($2);
	} |
	expr {
		AstNode *node = new AstNode(AST_EDGE);
		ast_stack.back()->children.push_back(node);
		node->children.push_back($1);
	};
"""
def p_always_event(p):
	"""always_event : TOK_POSEDGE expr
	| TOK_NEGEDGE expr
	| expr
	"""
	p[0] = None
"""
opt_label:
	':' TOK_ID {
		$$ = $2;
	} |
	/* empty */ {
		$$ = NULL;
	};
"""
def p_label(p):
	"""label : ':' TOK_ID
	"""
	p[0] = p[1]
"""
opt_sva_label:
	TOK_SVA_LABEL ':' {
		$$ = $1;
	} |
	/* empty */ {
		$$ = NULL;
	};

opt_property:
	TOK_PROPERTY {
		$$ = true;
	} |
	TOK_FINAL {
		$$ = false;
	} |
	/* empty */ {
		$$ = false;
	};

modport_stmt:
    TOK_MODPORT TOK_ID {
        AstNode *modport = new AstNode(AST_MODPORT);
        ast_stack.back()->children.push_back(modport);
        ast_stack.push_back(modport);
        modport->str = *$2;
        delete $2;
    }  modport_args_opt {
        ast_stack.pop_back();
        log_assert(ast_stack.size() == 2);
    } ';'
"""
def p_modport_stmt(p):
	"""modport_stmt : TOK_MODPORT TOK_ID '(' ')' ';'
	| TOK_MODPORT TOK_ID '(' modport_arg_LSEQ ')' ';'
	"""
	p[0] = None
"""
modport_args_opt:
    '(' ')' | '(' modport_args optional_comma ')';

modport_args:
    modport_arg | modport_args ',' modport_arg;

modport_arg:
    modport_type_token modport_member |
    modport_member
"""
def p_modport_arg(p):
	"""modport_arg : TOK_INPUT TOK_ID
	| TOK_OUTPUT TOK_ID
	"""
	p[0] = None
"""
modport_member:
    TOK_ID {
        AstNode *modport_member = new AstNode(AST_MODPORTMEMBER);
        ast_stack.back()->children.push_back(modport_member);
        modport_member->str = *$1;
        modport_member->is_input = current_modport_input;
        modport_member->is_output = current_modport_output;
        delete $1;
    }

modport_type_token:
    TOK_INPUT {current_modport_input = 1; current_modport_output = 0;} | TOK_OUTPUT {current_modport_input = 0; current_modport_output = 1;}

assert:
	opt_sva_label TOK_ASSERT opt_property '(' expr ')' ';' {
		if (noassert_mode) {
			delete $5;
		} else {
			AstNode *node = new AstNode(assume_asserts_mode ? AST_ASSUME : AST_ASSERT, $5);
			SET_AST_NODE_LOC(node, @1, @6);
			if ($1 != nullptr)
				node->str = *$1;
			ast_stack.back()->children.push_back(node);
		}
		if ($1 != nullptr)
			delete $1;
	} |
	opt_sva_label TOK_ASSUME opt_property '(' expr ')' ';' {
		if (noassume_mode) {
			delete $5;
		} else {
			AstNode *node = new AstNode(assert_assumes_mode ? AST_ASSERT : AST_ASSUME, $5);
			SET_AST_NODE_LOC(node, @1, @6);
			if ($1 != nullptr)
				node->str = *$1;
			ast_stack.back()->children.push_back(node);
		}
		if ($1 != nullptr)
			delete $1;
	} |
	opt_sva_label TOK_ASSERT opt_property '(' TOK_EVENTUALLY expr ')' ';' {
		if (noassert_mode) {
			delete $6;
		} else {
			AstNode *node = new AstNode(assume_asserts_mode ? AST_FAIR : AST_LIVE, $6);
			SET_AST_NODE_LOC(node, @1, @7);
			if ($1 != nullptr)
				node->str = *$1;
			ast_stack.back()->children.push_back(node);
		}
		if ($1 != nullptr)
			delete $1;
	} |
	opt_sva_label TOK_ASSUME opt_property '(' TOK_EVENTUALLY expr ')' ';' {
		if (noassume_mode) {
			delete $6;
		} else {
			AstNode *node = new AstNode(assert_assumes_mode ? AST_LIVE : AST_FAIR, $6);
			SET_AST_NODE_LOC(node, @1, @7);
			if ($1 != nullptr)
				node->str = *$1;
			ast_stack.back()->children.push_back(node);
		}
		if ($1 != nullptr)
			delete $1;
	} |
	opt_sva_label TOK_COVER opt_property '(' expr ')' ';' {
		AstNode *node = new AstNode(AST_COVER, $5);
		SET_AST_NODE_LOC(node, @1, @6);
		if ($1 != nullptr) {
			node->str = *$1;
			delete $1;
		}
		ast_stack.back()->children.push_back(node);
	} |
	opt_sva_label TOK_COVER opt_property '(' ')' ';' {
		AstNode *node = new AstNode(AST_COVER, AstNode::mkconst_int(1, false));
		SET_AST_NODE_LOC(node, @1, @5);
		if ($1 != nullptr) {
			node->str = *$1;
			delete $1;
		}
		ast_stack.back()->children.push_back(node);
	} |
	opt_sva_label TOK_COVER ';' {
		AstNode *node = new AstNode(AST_COVER, AstNode::mkconst_int(1, false));
		SET_AST_NODE_LOC(node, @1, @2);
		if ($1 != nullptr) {
			node->str = *$1;
			delete $1;
		}
		ast_stack.back()->children.push_back(node);
	} |
	opt_sva_label TOK_RESTRICT opt_property '(' expr ')' ';' {
		if (norestrict_mode) {
			delete $5;
		} else {
			AstNode *node = new AstNode(AST_ASSUME, $5);
			SET_AST_NODE_LOC(node, @1, @6);
			if ($1 != nullptr)
				node->str = *$1;
			ast_stack.back()->children.push_back(node);
		}
		if (!$3)
			log_file_warning(current_filename, get_line_num(), "SystemVerilog does not allow \"restrict\" without \"property\".\n");
		if ($1 != nullptr)
			delete $1;
	} |
	opt_sva_label TOK_RESTRICT opt_property '(' TOK_EVENTUALLY expr ')' ';' {
		if (norestrict_mode) {
			delete $6;
		} else {
			AstNode *node = new AstNode(AST_FAIR, $6);
			SET_AST_NODE_LOC(node, @1, @7);
			if ($1 != nullptr)
				node->str = *$1;
			ast_stack.back()->children.push_back(node);
		}
		if (!$3)
			log_file_warning(current_filename, get_line_num(), "SystemVerilog does not allow \"restrict\" without \"property\".\n");
		if ($1 != nullptr)
			delete $1;
	};
"""
def p_assert(p):
	"""assert : TOK_ASSUME '(' expr ')' ';'
	| TOK_ASSUME '(' TOK_EVENTUALLY expr ')' ';'
	| TOK_ASSERT '(' expr ')' ';'
	| TOK_ASSERT '(' TOK_EVENTUALLY expr ')' ';'
	| TOK_ID ':' TOK_RESTRICT TOK_PROPERTY '(' expr ')' ';'
	"""
	p[0] = None
"""
assert_property:
	opt_sva_label TOK_ASSERT TOK_PROPERTY '(' expr ')' ';' {
		AstNode *node = new AstNode(assume_asserts_mode ? AST_ASSUME : AST_ASSERT, $5);
		SET_AST_NODE_LOC(node, @1, @6);
		ast_stack.back()->children.push_back(node);
		if ($1 != nullptr) {
			ast_stack.back()->children.back()->str = *$1;
			delete $1;
		}
	} |
	opt_sva_label TOK_ASSUME TOK_PROPERTY '(' expr ')' ';' {
		AstNode *node = new AstNode(AST_ASSUME, $5);
		SET_AST_NODE_LOC(node, @1, @6);
		ast_stack.back()->children.push_back(node);
		if ($1 != nullptr) {
			ast_stack.back()->children.back()->str = *$1;
			delete $1;
		}
	} |
	opt_sva_label TOK_ASSERT TOK_PROPERTY '(' TOK_EVENTUALLY expr ')' ';' {
		AstNode *node = new AstNode(assume_asserts_mode ? AST_FAIR : AST_LIVE, $6);
		SET_AST_NODE_LOC(node, @1, @7);
		ast_stack.back()->children.push_back(node);
		if ($1 != nullptr) {
			ast_stack.back()->children.back()->str = *$1;
			delete $1;
		}
	} |
	opt_sva_label TOK_ASSUME TOK_PROPERTY '(' TOK_EVENTUALLY expr ')' ';' {
		AstNode *node = new AstNode(AST_FAIR, $6);
		SET_AST_NODE_LOC(node, @1, @7);
		ast_stack.back()->children.push_back(node);
		if ($1 != nullptr) {
			ast_stack.back()->children.back()->str = *$1;
			delete $1;
		}
	} |
	opt_sva_label TOK_COVER TOK_PROPERTY '(' expr ')' ';' {
		AstNode *node = new AstNode(AST_COVER, $5);
		SET_AST_NODE_LOC(node, @1, @6);
		ast_stack.back()->children.push_back(node);
		if ($1 != nullptr) {
			ast_stack.back()->children.back()->str = *$1;
			delete $1;
		}
	} |
	opt_sva_label TOK_RESTRICT TOK_PROPERTY '(' expr ')' ';' {
		if (norestrict_mode) {
			delete $5;
		} else {
			AstNode *node = new AstNode(AST_ASSUME, $5);
			SET_AST_NODE_LOC(node, @1, @6);
			ast_stack.back()->children.push_back(node);
			if ($1 != nullptr) {
				ast_stack.back()->children.back()->str = *$1;
				delete $1;
			}
		}
	} |
	opt_sva_label TOK_RESTRICT TOK_PROPERTY '(' TOK_EVENTUALLY expr ')' ';' {
		if (norestrict_mode) {
			delete $6;
		} else {
			AstNode *node = new AstNode(AST_FAIR, $6);
			SET_AST_NODE_LOC(node, @1, @7);
			ast_stack.back()->children.push_back(node);
			if ($1 != nullptr) {
				ast_stack.back()->children.back()->str = *$1;
				delete $1;
			}
		}
	};

simple_behavioral_stmt:
	lvalue '=' delay expr {
		AstNode *node = new AstNode(AST_ASSIGN_EQ, $1, $4);
		ast_stack.back()->children.push_back(node);
		SET_AST_NODE_LOC(node, @1, @4);
	} |
	lvalue TOK_INCREMENT {
		AstNode *node = new AstNode(AST_ASSIGN_EQ, $1, new AstNode(AST_ADD, $1->clone(), AstNode::mkconst_int(1, true)));
		ast_stack.back()->children.push_back(node);
		SET_AST_NODE_LOC(node, @1, @2);
	} |
	lvalue TOK_DECREMENT {
		AstNode *node = new AstNode(AST_ASSIGN_EQ, $1, new AstNode(AST_SUB, $1->clone(), AstNode::mkconst_int(1, true)));
		ast_stack.back()->children.push_back(node);
		SET_AST_NODE_LOC(node, @1, @2);
	} |
	lvalue OP_LE delay expr {
		AstNode *node = new AstNode(AST_ASSIGN_LE, $1, $4);
		ast_stack.back()->children.push_back(node);
		SET_AST_NODE_LOC(node, @1, @4);
	};
"""
def p_simple_behavioral_stmt(p):
	"""simple_behavioral_stmt : lvalue '=' delay_OPT expr
	| lvalue TOK_INCREMENT
	| lvalue TOK_DECREMENT
	| lvalue OP_LE delay_OPT expr
	"""
	p[0] = None
"""
// this production creates the obligatory if-else shift/reduce conflict
behavioral_stmt:
	defattr | assert | wire_decl | param_decl | localparam_decl | typedef_decl |
	non_opt_delay behavioral_stmt |
	simple_behavioral_stmt ';' | ';' |
	hierarchical_id attr {
		AstNode *node = new AstNode(AST_TCALL);
		node->str = *$1;
		delete $1;
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
		append_attr(node, $2);
	} opt_arg_list ';'{
		ast_stack.pop_back();
	} |
	TOK_MSG_TASKS attr {
		AstNode *node = new AstNode(AST_TCALL);
		node->str = *$1;
		delete $1;
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
		append_attr(node, $2);
	} opt_arg_list ';'{
		ast_stack.pop_back();
	} |
	attr TOK_BEGIN {
		enterTypeScope();
	} opt_label {
		AstNode *node = new AstNode(AST_BLOCK);
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
		append_attr(node, $1);
		if ($4 != NULL)
			node->str = *$4;
	} behavioral_stmt_list TOK_END opt_label {
		exitTypeScope();
		if ($4 != NULL && $8 != NULL && *$4 != *$8)
			frontend_verilog_yyerror("Begin label (%s) and end label (%s) don't match.", $4->c_str()+1, $8->c_str()+1);
		delete $4;
		delete $8;
		ast_stack.pop_back();
	} |
	attr TOK_FOR '(' {
		AstNode *node = new AstNode(AST_FOR);
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
		append_attr(node, $1);
	} simple_behavioral_stmt ';' expr {
		ast_stack.back()->children.push_back($7);
	} ';' simple_behavioral_stmt ')' {
		AstNode *block = new AstNode(AST_BLOCK);
		ast_stack.back()->children.push_back(block);
		ast_stack.push_back(block);
	} behavioral_stmt {
		SET_AST_NODE_LOC(ast_stack.back(), @13, @13);
		ast_stack.pop_back();
		SET_AST_NODE_LOC(ast_stack.back(), @2, @13);
		ast_stack.pop_back();
	} |
	attr TOK_WHILE '(' expr ')' {
		AstNode *node = new AstNode(AST_WHILE);
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
		append_attr(node, $1);
		AstNode *block = new AstNode(AST_BLOCK);
		ast_stack.back()->children.push_back($4);
		ast_stack.back()->children.push_back(block);
		ast_stack.push_back(block);
	} behavioral_stmt {
		SET_AST_NODE_LOC(ast_stack.back(), @7, @7);
		ast_stack.pop_back();
		ast_stack.pop_back();
	} |
	attr TOK_REPEAT '(' expr ')' {
		AstNode *node = new AstNode(AST_REPEAT);
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
		append_attr(node, $1);
		AstNode *block = new AstNode(AST_BLOCK);
		ast_stack.back()->children.push_back($4);
		ast_stack.back()->children.push_back(block);
		ast_stack.push_back(block);
	} behavioral_stmt {
		SET_AST_NODE_LOC(ast_stack.back(), @7, @7);
		ast_stack.pop_back();
		ast_stack.pop_back();
	} |
	attr TOK_IF '(' expr ')' {
		AstNode *node = new AstNode(AST_CASE);
		AstNode *block = new AstNode(AST_BLOCK);
		AstNode *cond = new AstNode(AST_COND, AstNode::mkconst_int(1, false, 1), block);
		SET_AST_NODE_LOC(cond, @4, @4);
		ast_stack.back()->children.push_back(node);
		node->children.push_back(new AstNode(AST_REDUCE_BOOL, $4));
		node->children.push_back(cond);
		ast_stack.push_back(node);
		ast_stack.push_back(block);
		append_attr(node, $1);
	} behavioral_stmt {
		SET_AST_NODE_LOC(ast_stack.back(), @7, @7);
	} optional_else {
		ast_stack.pop_back();
		SET_AST_NODE_LOC(ast_stack.back(), @2, @9);
		ast_stack.pop_back();
	} |
	case_attr case_type '(' expr ')' {
		AstNode *node = new AstNode(AST_CASE, $4);
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
		append_attr(node, $1);
		SET_AST_NODE_LOC(ast_stack.back(), @4, @4);
	} opt_synopsys_attr case_body TOK_ENDCASE {
		SET_AST_NODE_LOC(ast_stack.back(), @2, @9);
		case_type_stack.pop_back();
		ast_stack.pop_back();
	};

	;
"""
def p_behavioral_stmt(p):
	"""behavioral_stmt : ';'
	| simple_behavioral_stmt ';'
	| delay behavioral_stmt
	| assert
	| hierarchical_id attr_STAR ';'
	| hierarchical_id attr_STAR '(' ')' ';'
	| hierarchical_id attr_STAR '(' expr_SEQ ')' ';'
	| wire_decl
	| attr_STAR TOK_BEGIN label_OPT behavioral_stmt_STAR TOK_END
	| TOK_FOREVER TOK_BEGIN label_OPT behavioral_stmt_STAR TOK_END
	| attr_STAR TOK_IF '(' expr ')' behavioral_stmt
	| attr_STAR TOK_IF '(' expr ')' behavioral_stmt TOK_ELSE behavioral_stmt 
	| case_attr case_type '(' expr ')' opt_synopsys_attr case_item_STAR TOK_ENDCASE
	| attr_STAR TOK_FOR '(' simple_behavioral_stmt ';' expr ';' simple_behavioral_stmt ')' behavioral_stmt
	| attr_STAR TOK_WHILE '(' expr ')' behavioral_stmt
	| attr_STAR TOK_REPEAT '(' expr ')' behavioral_stmt
	| TOK_TRIG TOK_ID ';'
	"""
	p[0] = p[1]
"""
	| TOK_REPEAT '(' expr ')' '@' '(' always_events ')' ';'
	| TOK_WHILE '(' expr ')' TOK_BEGIN '@' '(' always_events ')' ';' behavioral_stmt TOK_END
	| TOK_REPEAT '(' expr ')' always_cond
"""
"""
unique_case_attr:
	/* empty */ {
		$$ = false;
	} |
	TOK_PRIORITY case_attr {
		$$ = $2;
	} |
	TOK_UNIQUE case_attr {
		$$ = true;
	};
"""
def p_unique_case_attr(p):
	"""unique_case_attr :
	| TOK_PRIORITY case_attr
	| TOK_UNIQUE case_attr
	"""
	p[0] = None
"""
case_attr:
	attr unique_case_attr {
		if ($2) (*$1)["\\parallel_case"] = AstNode::mkconst_int(1, false);
		$$ = $1;
	};
"""
def p_case_attr(p):
	"""case_attr : attr_STAR unique_case_attr
	"""
	p[0] = None
"""
case_type:
	TOK_CASE {
		case_type_stack.push_back(0);
	} |
	TOK_CASEX {
		case_type_stack.push_back('x');
	} |
	TOK_CASEZ {
		case_type_stack.push_back('z');
	};
"""
def p_case_type(p):
	"""case_type : TOK_CASE
	| TOK_CASEX
	| TOK_CASEZ
	"""
	p[0] = p[1]
"""
opt_synopsys_attr:
	opt_synopsys_attr TOK_SYNOPSYS_FULL_CASE {
		if (ast_stack.back()->attributes.count(ID::full_case) == 0)
			ast_stack.back()->attributes[ID::full_case] = AstNode::mkconst_int(1, false);
	} |
	opt_synopsys_attr TOK_SYNOPSYS_PARALLEL_CASE {
		if (ast_stack.back()->attributes.count(ID::parallel_case) == 0)
			ast_stack.back()->attributes[ID::parallel_case] = AstNode::mkconst_int(1, false);
	} |
	/* empty */;
"""
def p_opt_synopsys_attr(p):
	"""opt_synopsys_attr :
	"""
	p[0] = None
	
"""
behavioral_stmt_list:
	behavioral_stmt_list behavioral_stmt |
	/* empty */;

optional_else:
	TOK_ELSE {
		AstNode *block = new AstNode(AST_BLOCK);
		AstNode *cond = new AstNode(AST_COND, new AstNode(AST_DEFAULT), block);
		SET_AST_NODE_LOC(cond, @1, @1);

		ast_stack.pop_back();
		ast_stack.back()->children.push_back(cond);
		ast_stack.push_back(block);
	} behavioral_stmt {
		SET_AST_NODE_LOC(ast_stack.back(), @3, @3);
	} |
	/* empty */ %prec FAKE_THEN;

case_body:
	case_body case_item |
	/* empty */;

case_item:
	{
		AstNode *node = new AstNode(
				case_type_stack.size() && case_type_stack.back() == 'x' ? AST_CONDX :
				case_type_stack.size() && case_type_stack.back() == 'z' ? AST_CONDZ : AST_COND);
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
	} case_select {
		AstNode *block = new AstNode(AST_BLOCK);
		ast_stack.back()->children.push_back(block);
		ast_stack.push_back(block);
		case_type_stack.push_back(0);
	} behavioral_stmt {
		case_type_stack.pop_back();
		SET_AST_NODE_LOC(ast_stack.back(), @4, @4);
		ast_stack.pop_back();
		ast_stack.pop_back();
	};
"""
def p_case_item(p):
	"""case_item : case_select behavioral_stmt
	"""
	p[0] = None
"""
gen_case_body:
	gen_case_body gen_case_item |
	/* empty */;

gen_case_item:
	{
		AstNode *node = new AstNode(
				case_type_stack.size() && case_type_stack.back() == 'x' ? AST_CONDX :
				case_type_stack.size() && case_type_stack.back() == 'z' ? AST_CONDZ : AST_COND);
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
	} case_select {
		case_type_stack.push_back(0);
		SET_AST_NODE_LOC(ast_stack.back(), @2, @2);
	} gen_stmt_or_null {
		case_type_stack.pop_back();
		ast_stack.pop_back();
	};
"""
def p_gen_case_item(p):
	"""gen_case_item : case_select gen_stmt_or_module_body_stmt
	| case_select ';'
	"""
	p[0] = None
"""
case_select:
	case_expr_list ':' |
	TOK_DEFAULT;
"""
def p_case_select(p):
	"""case_select : expr_SEQ ':'
	| TOK_DEFAULT ':'
	| TOK_DEFAULT
	"""
	p[0] = None
"""
case_expr_list:
	TOK_DEFAULT {
		AstNode *node = new AstNode(AST_DEFAULT);
		SET_AST_NODE_LOC(node, @1, @1);
		ast_stack.back()->children.push_back(node);
	} |
	TOK_SVA_LABEL {
		AstNode *node = new AstNode(AST_IDENTIFIER);
		SET_AST_NODE_LOC(node, @1, @1);
		ast_stack.back()->children.push_back(node);
		ast_stack.back()->children.back()->str = *$1;
		delete $1;
	} |
	expr {
		ast_stack.back()->children.push_back($1);
	} |
	case_expr_list ',' expr {
		ast_stack.back()->children.push_back($3);
	};
"""
#def p_case_expr_list(p):
#	"""case_expr_list : TOK_DEFAULT
#	| TOK_SVA_LABEL
#	| expr
#	| case_expr_list ',' expr
#	"""
#	p[0] = None
"""
rvalue:
	hierarchical_id '[' expr ']' '.' rvalue {
		$$ = new AstNode(AST_PREFIX, $3, $6);
		$$->str = *$1;
		delete $1;
	} |
	hierarchical_id range {
		$$ = new AstNode(AST_IDENTIFIER, $2);
		$$->str = *$1;
		SET_AST_NODE_LOC($$, @1, @1);
		delete $1;
		if ($2 == nullptr && ($$->str == "\\$initstate" ||
				$$->str == "\\$anyconst" || $$->str == "\\$anyseq" ||
				$$->str == "\\$allconst" || $$->str == "\\$allseq"))
			$$->type = AST_FCALL;
	} |
	hierarchical_id non_opt_multirange {
		$$ = new AstNode(AST_IDENTIFIER, $2);
		$$->str = *$1;
		SET_AST_NODE_LOC($$, @1, @1);
		delete $1;
	};
"""
def p_rvalue(p):
	"""rvalue : hierarchical_id '[' expr ']' '.' rvalue
	| hierarchical_id range_OPT
	| hierarchical_id multirange
	"""
	p[0] = None
"""
lvalue:
	rvalue {
		$$ = $1;
	} |
	'{' lvalue_concat_list '}' {
		$$ = $2;
	};
"""
def p_lvalue(p):
	"""lvalue : rvalue
	| '{' expr_SEQ '}'
	"""
	p[0] = None
"""
lvalue_concat_list:
	expr {
		$$ = new AstNode(AST_CONCAT);
		$$->children.push_back($1);
	} |
	expr ',' lvalue_concat_list {
		$$ = $3;
		$$->children.push_back($1);
	};

opt_arg_list:
	'(' arg_list optional_comma ')' |
	/* empty */;

arg_list:
	arg_list2 |
	/* empty */;

arg_list2:
	single_arg |
	arg_list ',' single_arg;

single_arg:
	expr {
		ast_stack.back()->children.push_back($1);
	};

module_gen_body:
	module_gen_body gen_stmt_or_module_body_stmt |
	/* empty */;

gen_stmt_or_module_body_stmt:
	gen_stmt | module_body_stmt;
"""
def p_gen_stmt_or_module_body_stmt(p):
	"""gen_stmt_or_module_body_stmt : gen_stmt
	| module_body_stmt
	"""
	p[0] = p[1]
"""
// this production creates the obligatory if-else shift/reduce conflict
gen_stmt:
	TOK_FOR '(' {
		AstNode *node = new AstNode(AST_GENFOR);
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
	} simple_behavioral_stmt ';' expr {
		ast_stack.back()->children.push_back($6);
	} ';' simple_behavioral_stmt ')' gen_stmt_block {
		SET_AST_NODE_LOC(ast_stack.back(), @1, @11);
		ast_stack.pop_back();
	} |
	TOK_IF '(' expr ')' {
		AstNode *node = new AstNode(AST_GENIF);
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
		ast_stack.back()->children.push_back($3);
	} gen_stmt_block opt_gen_else {
		SET_AST_NODE_LOC(ast_stack.back(), @1, @7);
		ast_stack.pop_back();
	} |
	case_type '(' expr ')' {
		AstNode *node = new AstNode(AST_GENCASE, $3);
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
	} gen_case_body TOK_ENDCASE {
		case_type_stack.pop_back();
		SET_AST_NODE_LOC(ast_stack.back(), @1, @7);
		ast_stack.pop_back();
	} |
	TOK_BEGIN {
		enterTypeScope();
	} opt_label {
		AstNode *node = new AstNode(AST_GENBLOCK);
		node->str = $3 ? *$3 : std::string();
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
	} module_gen_body TOK_END opt_label {
		exitTypeScope();
		delete $3;
		delete $7;
		SET_AST_NODE_LOC(ast_stack.back(), @1, @7);
		ast_stack.pop_back();
	} |
	TOK_MSG_TASKS {
		AstNode *node = new AstNode(AST_TECALL);
		node->str = *$1;
		delete $1;
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
	} opt_arg_list ';'{
		SET_AST_NODE_LOC(ast_stack.back(), @1, @3);
		ast_stack.pop_back();
	};
"""
def p_gen_stmt(p):
	"""gen_stmt : TOK_FOR '(' simple_behavioral_stmt ';' expr ';' simple_behavioral_stmt ')' gen_stmt_or_module_body_stmt
	| TOK_IF '(' expr ')' gen_stmt_or_module_body_stmt
	| TOK_IF '(' expr ')' gen_stmt_or_module_body_stmt TOK_ELSE gen_stmt_or_module_body_stmt
	| TOK_IF '(' expr ')' gen_stmt_or_module_body_stmt TOK_ELSE ';'
	| case_type '(' expr ')' gen_case_item_STAR TOK_ENDCASE
	| TOK_BEGIN label_OPT gen_stmt_or_module_body_stmt_STAR TOK_END
	"""
	p[0] = None
"""
gen_stmt_block:
	{
		AstNode *node = new AstNode(AST_GENBLOCK);
		ast_stack.back()->children.push_back(node);
		ast_stack.push_back(node);
	} gen_stmt_or_module_body_stmt {
		SET_AST_NODE_LOC(ast_stack.back(), @2, @2);
		ast_stack.pop_back();
	};

gen_stmt_or_null:
	gen_stmt_block | ';';

opt_gen_else:
	TOK_ELSE gen_stmt_or_null | /* empty */ %prec FAKE_THEN;

expr:
	basic_expr {
		$$ = $1;
	} |
	basic_expr '?' attr expr ':' expr {
		$$ = new AstNode(AST_TERNARY);
		$$->children.push_back($1);
		$$->children.push_back($4);
		$$->children.push_back($6);
		SET_AST_NODE_LOC($$, @1, @$);
		append_attr($$, $3);
	};
"""
def p_expr(p):
	"""expr : expr13
	"""
	p[0] = p[1]
"""
basic_expr:
	rvalue {
		$$ = $1;
	} |
	'(' expr ')' integral_number {
		if ($4->compare(0, 1, "'") != 0)
			frontend_verilog_yyerror("Cast operation must be applied on sized constants e.g. (<expr>)<constval> , while %s is not a sized constant.", $4->c_str());
		AstNode *bits = $2;
		AstNode *val = const2ast(*$4, case_type_stack.size() == 0 ? 0 : case_type_stack.back(), !lib_mode);
		if (val == NULL)
			log_error("Value conversion failed: `%s'\n", $4->c_str());
		$$ = new AstNode(AST_TO_BITS, bits, val);
		delete $4;
	} |
	hierarchical_id integral_number {
		if ($2->compare(0, 1, "'") != 0)
			frontend_verilog_yyerror("Cast operation must be applied on sized constants, e.g. <ID>\'d0, while %s is not a sized constant.", $2->c_str());
		AstNode *bits = new AstNode(AST_IDENTIFIER);
		bits->str = *$1;
		SET_AST_NODE_LOC(bits, @1, @1);
		AstNode *val = const2ast(*$2, case_type_stack.size() == 0 ? 0 : case_type_stack.back(), !lib_mode);
		if (val == NULL)
			log_error("Value conversion failed: `%s'\n", $2->c_str());
		$$ = new AstNode(AST_TO_BITS, bits, val);
		delete $1;
		delete $2;
	} |
	integral_number {
		$$ = const2ast(*$1, case_type_stack.size() == 0 ? 0 : case_type_stack.back(), !lib_mode);
		if ($$ == NULL)
			log_error("Value conversion failed: `%s'\n", $1->c_str());
		delete $1;
	} |
	TOK_REALVAL {
		$$ = new AstNode(AST_REALVALUE);
		char *p = (char*)malloc(GetSize(*$1) + 1), *q;
		for (int i = 0, j = 0; j < GetSize(*$1); j++)
			if ((*$1)[j] != '_')
				p[i++] = (*$1)[j], p[i] = 0;
		$$->realvalue = strtod(p, &q);
		SET_AST_NODE_LOC($$, @1, @1);
		log_assert(*q == 0);
		delete $1;
		free(p);
	} |
	TOK_STRING {
		$$ = AstNode::mkconst_str(*$1);
		delete $1;
	} |
	hierarchical_id attr {
		AstNode *node = new AstNode(AST_FCALL);
		node->str = *$1;
		delete $1;
		ast_stack.push_back(node);
		SET_AST_NODE_LOC(node, @1, @1);
		append_attr(node, $2);
	} '(' arg_list optional_comma ')' {
		$$ = ast_stack.back();
		ast_stack.pop_back();
	} |
	TOK_TO_SIGNED attr '(' expr ')' {
		$$ = new AstNode(AST_TO_SIGNED, $4);
		append_attr($$, $2);
	} |
	TOK_TO_UNSIGNED attr '(' expr ')' {
		$$ = new AstNode(AST_TO_UNSIGNED, $4);
		append_attr($$, $2);
	} |
	'(' expr ')' {
		$$ = $2;
	} |
	'(' expr ':' expr ':' expr ')' {
		delete $2;
		$$ = $4;
		delete $6;
	} |
	'{' concat_list '}' {
		$$ = $2;
	} |
	'{' expr '{' concat_list '}' '}' {
		$$ = new AstNode(AST_REPLICATE, $2, $4);
	} |
	'~' attr basic_expr %prec UNARY_OPS {
		$$ = new AstNode(AST_BIT_NOT, $3);
		SET_AST_NODE_LOC($$, @1, @3);
		append_attr($$, $2);
	} |
	basic_expr '&' attr basic_expr {
		$$ = new AstNode(AST_BIT_AND, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr OP_NAND attr basic_expr {
		$$ = new AstNode(AST_BIT_NOT, new AstNode(AST_BIT_AND, $1, $4));
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr '|' attr basic_expr {
		$$ = new AstNode(AST_BIT_OR, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr OP_NOR attr basic_expr {
		$$ = new AstNode(AST_BIT_NOT, new AstNode(AST_BIT_OR, $1, $4));
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr '^' attr basic_expr {
		$$ = new AstNode(AST_BIT_XOR, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr OP_XNOR attr basic_expr {
		$$ = new AstNode(AST_BIT_XNOR, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	'&' attr basic_expr %prec UNARY_OPS {
		$$ = new AstNode(AST_REDUCE_AND, $3);
		SET_AST_NODE_LOC($$, @1, @3);
		append_attr($$, $2);
	} |
	OP_NAND attr basic_expr %prec UNARY_OPS {
		$$ = new AstNode(AST_REDUCE_AND, $3);
		SET_AST_NODE_LOC($$, @1, @3);
		append_attr($$, $2);
		$$ = new AstNode(AST_LOGIC_NOT, $$);
	} |
	'|' attr basic_expr %prec UNARY_OPS {
		$$ = new AstNode(AST_REDUCE_OR, $3);
		SET_AST_NODE_LOC($$, @1, @3);
		append_attr($$, $2);
	} |
	OP_NOR attr basic_expr %prec UNARY_OPS {
		$$ = new AstNode(AST_REDUCE_OR, $3);
		SET_AST_NODE_LOC($$, @1, @3);
		append_attr($$, $2);
		$$ = new AstNode(AST_LOGIC_NOT, $$);
		SET_AST_NODE_LOC($$, @1, @3);
	} |
	'^' attr basic_expr %prec UNARY_OPS {
		$$ = new AstNode(AST_REDUCE_XOR, $3);
		SET_AST_NODE_LOC($$, @1, @3);
		append_attr($$, $2);
	} |
	OP_XNOR attr basic_expr %prec UNARY_OPS {
		$$ = new AstNode(AST_REDUCE_XNOR, $3);
		SET_AST_NODE_LOC($$, @1, @3);
		append_attr($$, $2);
	} |
	basic_expr OP_SHL attr basic_expr {
		$$ = new AstNode(AST_SHIFT_LEFT, $1, new AstNode(AST_TO_UNSIGNED, $4));
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr OP_SHR attr basic_expr {
		$$ = new AstNode(AST_SHIFT_RIGHT, $1, new AstNode(AST_TO_UNSIGNED, $4));
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr OP_SSHL attr basic_expr {
		$$ = new AstNode(AST_SHIFT_SLEFT, $1, new AstNode(AST_TO_UNSIGNED, $4));
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr OP_SSHR attr basic_expr {
		$$ = new AstNode(AST_SHIFT_SRIGHT, $1, new AstNode(AST_TO_UNSIGNED, $4));
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr '<' attr basic_expr {
		$$ = new AstNode(AST_LT, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr OP_LE attr basic_expr {
		$$ = new AstNode(AST_LE, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr OP_EQ attr basic_expr {
		$$ = new AstNode(AST_EQ, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr OP_NE attr basic_expr {
		$$ = new AstNode(AST_NE, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr OP_EQX attr basic_expr {
		$$ = new AstNode(AST_EQX, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr OP_NEX attr basic_expr {
		$$ = new AstNode(AST_NEX, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr OP_GE attr basic_expr {
		$$ = new AstNode(AST_GE, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr '>' attr basic_expr {
		$$ = new AstNode(AST_GT, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr '+' attr basic_expr {
		$$ = new AstNode(AST_ADD, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr '-' attr basic_expr {
		$$ = new AstNode(AST_SUB, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr '*' attr basic_expr {
		$$ = new AstNode(AST_MUL, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr '/' attr basic_expr {
		$$ = new AstNode(AST_DIV, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr '%' attr basic_expr {
		$$ = new AstNode(AST_MOD, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr OP_POW attr basic_expr {
		$$ = new AstNode(AST_POW, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	'+' attr basic_expr %prec UNARY_OPS {
		$$ = new AstNode(AST_POS, $3);
		SET_AST_NODE_LOC($$, @1, @3);
		append_attr($$, $2);
	} |
	'-' attr basic_expr %prec UNARY_OPS {
		$$ = new AstNode(AST_NEG, $3);
		SET_AST_NODE_LOC($$, @1, @3);
		append_attr($$, $2);
	} |
	basic_expr OP_LAND attr basic_expr {
		$$ = new AstNode(AST_LOGIC_AND, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	basic_expr OP_LOR attr basic_expr {
		$$ = new AstNode(AST_LOGIC_OR, $1, $4);
		SET_AST_NODE_LOC($$, @1, @4);
		append_attr($$, $3);
	} |
	'!' attr basic_expr %prec UNARY_OPS {
		$$ = new AstNode(AST_LOGIC_NOT, $3);
		SET_AST_NODE_LOC($$, @1, @3);
		append_attr($$, $2);
	};
"""
def p_basic_expr(p):
	"""basic_expr : rvalue
	| integral_number
	| TOK_REALVAL
	| TOK_STRING
	| '(' expr ')'
	| '{' expr_SEQ '}'
	| '{' expr '{' expr_SEQ '}' '}'
	| TOK_TO_SIGNED '(' expr ')'
	| TOK_TO_UNSIGNED '(' expr ')'
	| hierarchical_id attr_STAR '(' expr_SEQ ')'
	"""
	p[0] = None
"""
concat_list:
	expr {
		$$ = new AstNode(AST_CONCAT, $1);
	} |
	expr ',' concat_list {
		$$ = $3;
		$$->children.push_back($1);
	};

integral_number:
	TOK_CONSTVAL { $$ = $1; } |
	TOK_UNBASED_UNSIZED_CONSTVAL { $$ = $1; } |
	TOK_BASE TOK_BASED_CONSTVAL {
		$1->append(*$2);
		$$ = $1;
		delete $2;
	} |
	TOK_CONSTVAL TOK_BASE TOK_BASED_CONSTVAL {
		$1->append(*$2).append(*$3);
		$$ = $1;
		delete $2;
		delete $3;
	};
"""
def p_integral_number(p):
	"""integral_number : TOK_CONSTVAL
	| TOK_UNBASED_UNSIZED_CONSTVAL
	| TOK_BASED_CONSTVAL
	| TOK_CONSTVAL TOK_BASED_CONSTVAL
	"""
	p[0] = p[1]

############# operators ###################
"""
high to low :
	
1    + - ! ~ (unary)
2    **
3    * / %
4    + - (binary)
5    << >> <<< >>>
6    < <= > >=
7    == != === !==
8    & ~&
9    ^ ^~ ~^
10   | ~|
11   &&
12   ||
13   ?: (conditional operator)

All operators shall associate left to right with the exception of
the conditional operator, which shall associate right to left
"""

def p_expr1(p): ### plus les reduction ops
	"""expr1 : basic_expr
	| '+' expr1
	| '-' expr1
	| '!' attr_STAR expr1
	| '~' attr_STAR expr1
	| '&' expr1
	| OP_NAND expr1
	| '|' expr1
	| OP_NOR expr1
	| '^' expr1
	| OP_XNOR expr1
	"""
	p[0] = None

def p_expr2(p):
	"""expr2 : expr1
	| expr2 OP_POW expr1
	"""
	p[0] = None

def p_expr3(p):
	"""expr3 : expr2
	| expr3 '*' expr2
	| expr3 '/' expr2
	| expr3 '%' expr2
	"""
	p[0] = None

def p_expr4(p):
	"""expr4 : expr3
	| expr4 '+' attr_STAR expr3
	| expr4 '-' expr3
	"""
	p[0] = None

def p_expr5(p):
	"""expr5 : expr4
	| expr5 OP_SHL expr4
	| expr5 OP_SHR expr4
	| expr5 OP_SSHL expr4
	| expr5 OP_SSHR expr4
	"""
	p[0] = None

def p_expr6(p):
	"""expr6 : expr5
	| expr6 '<' expr5
	| expr6 '>' attr_STAR expr5
	| expr6 OP_LE expr5
	| expr6 OP_GE expr5
	"""
	p[0] = None

def p_expr7(p):
	"""expr7 : expr6
	| expr7 OP_EQ expr6
	| expr7 OP_NE expr6
	| expr7 OP_EQX expr6
	| expr7 OP_NEX expr6
	"""
	p[0] = None

def p_expr8(p):
	"""expr8 : expr7
	| expr8 '&' expr7
	| expr8 OP_NAND expr7
	"""
	p[0] = None

def p_expr9(p):
	"""expr9 : expr8
	| expr9 '^' expr8
	| expr9 OP_XNOR expr8
	"""
	p[0] = None

def p_expr10(p):
	"""expr10 : expr9
	| expr10 '|' expr9
	| expr10 OP_NOR expr9
	"""
	p[0] = None

def p_expr11(p):
	"""expr11 : expr10
	| expr11 OP_LAND attr_STAR expr10
	"""
	p[0] = None

def p_expr12(p):
	"""expr12 : expr11
	| expr12 OP_LOR attr_STAR expr11
	"""
	p[0] = None

def p_expr13(p):
	"""expr13 : expr12
	| expr12 '?' attr_STAR expr12 ':' expr13
	"""
	p[0] = None

############# iterators ##############
	
def p_assign_expr_SEQ(p):
	"""assign_expr_SEQ : assign_expr
	| assign_expr ',' assign_expr_SEQ
	"""
	make_seq_rr(p)

def p_attr_assign_SEQ(p):
	"""attr_assign_SEQ : attr_assign
	| attr_assign ',' attr_assign_SEQ_OPT
	"""
	make_seq_rr(p)
	
def p_attr_assign_SEQ_OPT(p):
	"""attr_assign_SEQ_OPT :
	| attr_assign_SEQ
	"""
	p[0] = [] if len(p) == 1 else p[1]

def p_attr_STAR(p):
	"""attr_STAR :
	| attr attr_STAR
	"""
	make_seq_rr(p)

def p_behavioral_stmt_STAR(p):
	"""behavioral_stmt_STAR :
	| behavioral_stmt behavioral_stmt_STAR
	"""
	make_seq_rr(p)

def p_case_item_STAR(p):
	"""case_item_STAR :
	| case_item case_item_STAR
	"""
	make_seq_rr(p)

def p_cell_parameter_list_OPT(p):
	"""cell_parameter_list_OPT :
	| cell_parameter_list
	"""
	p[0] = None if len(p) == 1 else p[1]

def p_cell_parameter_SEQ(p):
	"""cell_parameter_SEQ : cell_parameter
	| cell_parameter ',' cell_parameter_SEQ
	"""
	make_seq_rr(p)

def p_cell_port_SEQ(p):
	"""cell_port_SEQ : cell_port
	| cell_port ',' cell_port_SEQ
	"""
	make_seq_rr(p)
	
#def p_comma_OPT(p):
#	"""comma_OPT : 
#	| ','
#	"""
#	p[0] = None if len(p) == 1 else p[1]
	
def p_delay_OPT(p):
	"""delay_OPT : 
	| delay
	"""
	p[0] = None if len(p) == 1 else p[1]
	
def p_design_STAR(p):
	"""design_STAR :
	| design design_STAR
	"""
	make_seq_rr(p)

def p_enum_name_decl_SEQ(p):
	"""enum_name_decl_SEQ : enum_name_decl
	| enum_name_decl ',' enum_name_decl_SEQ
	"""
	make_seq_rr(p)

def p_expr_SEQ(p):
	"""expr_SEQ : expr
	| expr ',' expr_SEQ
	"""
	make_seq_rr(p)

def p_interface_body_stmt_STAR(p):
	"""interface_body_stmt_STAR :
	| interface_body_stmt interface_body_stmt_STAR
	"""
	make_seq_rr(p)
	
def p_gen_case_item_STAR(p):
	"""gen_case_item_STAR : 
	| gen_case_item gen_case_item_STAR
	"""
	make_seq_rr(p)

def p_gen_stmt_or_module_body_stmt_STAR(p):
	"""gen_stmt_or_module_body_stmt_STAR :
	| gen_stmt_or_module_body_stmt gen_stmt_or_module_body_stmt_STAR
	"""
	make_seq_rr(p)

def p_label_OPT(p):
	"""label_OPT :
	| label
	"""
	p[0] = None if len(p) == 1 else p[1]

def p_modport_arg_LSEQ(p):
	"""modport_arg_LSEQ : modport_arg
	| modport_arg_LSEQ ',' modport_arg
	"""
	make_seq_lr(p)

def p_module_arg_assignment_OPT(p):
	"""module_arg_assignment_OPT : 
	| module_arg_assignment
	"""
	p[0] = None if len(p) == 1 else p[1]

def p_module_arg_COMMA_STAR(p):
	"""module_arg_COMMA_STAR : 
	| module_arg_COMMA module_arg_COMMA_STAR
	"""
	make_seq_rr(p)

def p_module_arg_LSEQ(p):
	"""module_arg_LSEQ : module_arg
	| module_arg_LSEQ ',' module_arg
	"""
	make_seq_lr(p)

def p_module_arg_SEQ(p):
	"""module_arg_SEQ : module_arg
	| module_arg ',' module_arg_SEQ
	"""	
	make_seq_rr(p)
	
def p_module_args_OPT(p):
	"""module_args_OPT :
	| module_args
	"""
	p[0] = None if len(p) == 1 else p[1] 

def p_module_body_STAR(p):
	"""module_body_STAR :
	| module_body module_body_STAR
	"""
	make_seq_rr(p)

def p_module_para_OPT(p):
	"""module_para_OPT :
	| module_para
	"""
	p[0] = None if len(p) == 1 else p[1]

def p_package_body_stmt_STAR(p):
	"""package_body_stmt_STAR : 
	| package_body_stmt package_body_stmt_STAR
	"""
	make_seq_rr(p)

def p_range_OPT(p):
	"""range_OPT :
	| range
	"""
	p[0] = None if len(p) == 1 else p[1]

def p_range_PLUS(p):
	"""range_PLUS : range
	| range range_PLUS
	"""
	make_seq_rr(p)
	
def p_range_STAR(p):
	"""range_STAR :
	| range range_STAR
	"""
	make_seq_rr(p)

def p_single_cell_SEQ(p):
	"""single_cell_SEQ : single_cell
	| single_cell ',' single_cell_SEQ
	"""
	make_seq_rr(p)

def p_single_defparam_decl_SEQ(p):
	"""single_defparam_decl_SEQ : single_defparam_decl
	| single_defparam_decl ',' single_defparam_decl_SEQ
	"""
	make_seq_rr(p)

def p_single_module_para_SEQ(p):
	"""single_module_para_SEQ : single_module_para
	| single_module_para ',' single_module_para_SEQ
	"""
	make_seq_rr(p)

def p_single_param_decl_SEQ(p):
	"""single_param_decl_SEQ : single_param_decl
	| single_param_decl ',' single_param_decl_SEQ
	"""
	make_seq_rr(p)

def p_single_prim_SEQ(p):
	"""single_prim_SEQ : single_prim
	| single_prim ','  single_prim_SEQ
	"""
	make_seq_rr(p)

def p_specparam_assignment_SEQ(p):
	"""specparam_assignment_SEQ : specparam_assignment
	| specparam_assignment ',' specparam_assignment_SEQ
	"""
	make_seq_rr(p)

def p_TOK_AUTOMATIC_OPT(p):
	"""TOK_AUTOMATIC_OPT : 
	| TOK_AUTOMATIC
	"""
	p[0] = None if len(p) == 1 else p[1]

def p_TOK_ID_SEQ(p):
	"""TOK_ID_SEQ : TOK_ID
	| TOK_ID ',' TOK_ID_SEQ
	"""
	make_seq_rr(p)

def p_TOK_INTEGER_OPT(p):
	"""TOK_INTEGER_OPT :
	| TOK_INTEGER
	"""
	p[0] = None if len(p) == 1 else p[1]

def p_TOK_REAL_OPT(p):
	"""TOK_REAL_OPT :
	| TOK_REAL
	"""
	p[0] = None if len(p) == 1 else p[1]

def p_TOK_SIGNED_OPT(p):
	"""TOK_SIGNED_OPT :
	| TOK_SIGNED
	"""
	p[0] = None if len(p) == 1 else p[1]

def p_wire_name_and_opt_assign_SEQ(p):
	"""wire_name_and_opt_assign_SEQ : wire_name_and_opt_assign
	| wire_name_and_opt_assign ',' wire_name_and_opt_assign_SEQ
	"""
	make_seq_rr(p)

######### Error rule for syntax errors ###########

def p_error(p):
	print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
	# p est un ply.lex.LexToke,
	print('Syntax error at token ' + str(p))
	print('parser.symstack : ' + str(parser.symstack))
	print('parser.statestack : ' + str(parser.statestack))
	#assert False
	print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')

parser = yacc.yacc(optimize=0)
ply2yacc.yacc(optimize=0)

def parse_str(s):
	""
	lexer.lineno = 1
	result = parser.parse(s, lexer=lexer)
	return result

import verilog_preproc

def parse_file(fn, save_json = False):
	""
	macros_preproc = {}
	print('**  {}  **'.format(fn))
	encoding = 'latin-1' # 'utf-8'
	fd = open(fn, 'r',encoding=encoding)
	# s = fd.read()
	sl = verilog_preproc.pp(fd, **macros_preproc)
	s = ''.join(sl)
	fd.close()
	lexer.current_file = fn
	try:
		js = parse_str(s)
	except ply.lex.LexError:
		js = None
		print('!!!!!!!! LexError !!!!!')
	return js

if __name__ == '__main__':
	s = """
	module foo; supply0 bar; endmodule
	"""
	r = parser.parse(s, lexer = lexer)
	print(r)
	# 
	import codecs, os
	encoding = 'latin-1' # 'utf-8'
	fn = r'C:\Temp\github\yosys-tests-master\architecture'
	fn = r'C:\Temp\github\yosys-tests-master\backends'
	fn = r'C:\Temp\github\yosys-tests-master\bigsim'
	fn = r'C:\Temp\github\yosys-tests-master\equiv'
	fn = r'C:\Temp\github\yosys-tests-master\frontends'
	#fn = r'C:\Temp\github\yosys-tests-master\simple'
	#fn = r'C:\Temp\github\yosys-tests-master'
	for root, dirs, files in os.walk(fn):
		for file in files:
			if file.endswith('.v') and not (root.endswith('sim') and file == 'sieve.v'):
				fn = os.path.join(root,file)
				parse_file(fn)
