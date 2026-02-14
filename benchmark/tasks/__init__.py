from .find_definition import FindDefinitionTask
from .read_large_file import ReadLargeFileTask
from .edit_task import EditTask
from .codebase_navigation import CodebaseNavigationTask
from .markdown_section import MarkdownSectionTask
from .ripgrep_tasks import (
    RipgrepTraitImplementorsTask,
    RipgrepFlagDefinitionTask,
    RipgrepSearchDispatchTask,
    RipgrepWalkerParallelTask,
    RipgrepLineIterDefinitionTask,
    RipgrepLineIterUsageTask,
)
from .fastapi_tasks import (
    FastAPIDependencyResolutionTask,
    FastAPIRequestValidationTask,
    FastAPIDependsInternalsTask,
    FastAPIDependsFunctionTask,
    FastAPIDependsProcessingTask,
)
from .gin_tasks import (
    GinRadixTreeTask,
    GinClientIPTask,
    GinMiddlewareChainTask,
    GinContextNextTask,
    GinServeHTTPFlowTask,
)
from .express_tasks import (
    ExpressJsonSendTask,
    ExpressRenderChainTask,
    ExpressAppInitTask,
    ExpressResSendTask,
    ExpressAppRenderTask,
)

TASKS = {
    # Synthetic repo tasks
    "find_definition": FindDefinitionTask(),
    "read_large_file": ReadLargeFileTask(),
    "edit_task": EditTask(),
    "codebase_navigation": CodebaseNavigationTask(),
    "markdown_section": MarkdownSectionTask(),
    # ripgrep (Rust)
    "rg_trait_implementors": RipgrepTraitImplementorsTask(),
    "rg_flag_definition": RipgrepFlagDefinitionTask(),
    "rg_search_dispatch": RipgrepSearchDispatchTask(),
    "rg_walker_parallel": RipgrepWalkerParallelTask(),
    "rg_lineiter_definition": RipgrepLineIterDefinitionTask(),
    "rg_lineiter_usage": RipgrepLineIterUsageTask(),
    # fastapi (Python)
    "fastapi_dependency_resolution": FastAPIDependencyResolutionTask(),
    "fastapi_request_validation": FastAPIRequestValidationTask(),
    "fastapi_depends_internals": FastAPIDependsInternalsTask(),
    "fastapi_depends_function": FastAPIDependsFunctionTask(),
    "fastapi_depends_processing": FastAPIDependsProcessingTask(),
    # gin (Go)
    "gin_radix_tree": GinRadixTreeTask(),
    "gin_client_ip": GinClientIPTask(),
    "gin_middleware_chain": GinMiddlewareChainTask(),
    "gin_context_next": GinContextNextTask(),
    "gin_servehttp_flow": GinServeHTTPFlowTask(),
    # express (JavaScript)
    "express_json_send": ExpressJsonSendTask(),
    "express_render_chain": ExpressRenderChainTask(),
    "express_app_init": ExpressAppInitTask(),
    "express_res_send": ExpressResSendTask(),
    "express_app_render": ExpressAppRenderTask(),
}
