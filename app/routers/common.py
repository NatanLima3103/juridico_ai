from fastapi.templating import Jinja2Templates

from app.core.config import TEMPLATES_DIR


class CompatJinja2Templates(Jinja2Templates):
    def TemplateResponse(self, *args, **kwargs):
        if args and isinstance(args[0], str):
            name = args[0]
            context = args[1] if len(args) > 1 else kwargs.pop("context", None)
            if not isinstance(context, dict) or "request" not in context:
                raise ValueError("TemplateResponse antigo exige context com a chave 'request'.")
            request = context["request"]
            remaining_args = args[2:]
            return super().TemplateResponse(request, name, context, *remaining_args, **kwargs)

        return super().TemplateResponse(*args, **kwargs)


templates = CompatJinja2Templates(directory=str(TEMPLATES_DIR))
