#pragma once

#ifndef GLFW_INCLUDE_NONE
#define GLFW_INCLUDE_NONE
#endif
#include <GLFW/glfw3.h>

#include <cstddef>
#include <cstdint>

#ifndef APIENTRY
#ifdef _WIN32
#define APIENTRY __stdcall
#else
#define APIENTRY
#endif
#endif

namespace gl33 {

using GLenum = unsigned int;
using GLboolean = unsigned char;
using GLbitfield = unsigned int;
using GLint = int;
using GLuint = unsigned int;
using GLsizei = int;
using GLfloat = float;
using GLchar = char;
using GLsizeiptr = std::ptrdiff_t;
using GLintptr = std::ptrdiff_t;
using GLubyte = unsigned char;

constexpr GLboolean GL_FALSE_V = 0;
constexpr GLboolean GL_TRUE_V = 1;

constexpr GLbitfield GL_DEPTH_BUFFER_BIT_V = 0x00000100u;
constexpr GLbitfield GL_COLOR_BUFFER_BIT_V = 0x00004000u;

constexpr GLenum GL_TRIANGLES_V = 0x0004u;
constexpr GLenum GL_LINES_V = 0x0001u;
constexpr GLenum GL_LINE_STRIP_V = 0x0003u;
constexpr GLenum GL_DEPTH_TEST_V = 0x0B71u;
constexpr GLenum GL_BLEND_V = 0x0BE2u;
constexpr GLenum GL_SCISSOR_TEST_V = 0x0C11u;
constexpr GLenum GL_MULTISAMPLE_V = 0x809Du;
constexpr GLenum GL_LINE_SMOOTH_V = 0x0B20u;
constexpr GLenum GL_POLYGON_OFFSET_FILL_V = 0x8037u;
constexpr GLenum GL_SRC_ALPHA_V = 0x0302u;
constexpr GLenum GL_ONE_MINUS_SRC_ALPHA_V = 0x0303u;
constexpr GLenum GL_FLOAT_V = 0x1406u;
constexpr GLenum GL_UNSIGNED_INT_V = 0x1405u;
constexpr GLenum GL_UNSIGNED_BYTE_V = 0x1401u;
constexpr GLenum GL_RGBA_V = 0x1908u;
constexpr GLenum GL_RGBA8_V = 0x8058u;
constexpr GLenum GL_RGB_V = 0x1907u;
constexpr GLenum GL_DEPTH_COMPONENT24_V = 0x81A6u;
constexpr GLenum GL_DEPTH_ATTACHMENT_V = 0x8D00u;
constexpr GLenum GL_COLOR_ATTACHMENT0_V = 0x8CE0u;
constexpr GLenum GL_FRAMEBUFFER_V = 0x8D40u;
constexpr GLenum GL_RENDERBUFFER_V = 0x8D41u;
constexpr GLenum GL_FRAMEBUFFER_COMPLETE_V = 0x8CD5u;
constexpr GLenum GL_TEXTURE_2D_V = 0x0DE1u;
constexpr GLenum GL_TEXTURE_MIN_FILTER_V = 0x2801u;
constexpr GLenum GL_TEXTURE_MAG_FILTER_V = 0x2800u;
constexpr GLenum GL_TEXTURE_WRAP_S_V = 0x2802u;
constexpr GLenum GL_TEXTURE_WRAP_T_V = 0x2803u;
constexpr GLenum GL_LINEAR_V = 0x2601u;
constexpr GLenum GL_CLAMP_TO_EDGE_V = 0x812Fu;
constexpr GLenum GL_ARRAY_BUFFER_V = 0x8892u;
constexpr GLenum GL_ELEMENT_ARRAY_BUFFER_V = 0x8893u;
constexpr GLenum GL_DYNAMIC_DRAW_V = 0x88E8u;
constexpr GLenum GL_VERTEX_SHADER_V = 0x8B31u;
constexpr GLenum GL_FRAGMENT_SHADER_V = 0x8B30u;
constexpr GLenum GL_COMPILE_STATUS_V = 0x8B81u;
constexpr GLenum GL_LINK_STATUS_V = 0x8B82u;
constexpr GLenum GL_LESS_V = 0x0201u;
constexpr GLenum GL_LEQUAL_V = 0x0203u;

struct Dispatch {
    void(APIENTRY *Viewport)(GLint, GLint, GLsizei, GLsizei) = nullptr;
    void(APIENTRY *Scissor)(GLint, GLint, GLsizei, GLsizei) = nullptr;
    void(APIENTRY *ClearColor)(GLfloat, GLfloat, GLfloat, GLfloat) = nullptr;
    void(APIENTRY *Clear)(GLbitfield) = nullptr;
    void(APIENTRY *Enable)(GLenum) = nullptr;
    void(APIENTRY *Disable)(GLenum) = nullptr;
    void(APIENTRY *DepthFunc)(GLenum) = nullptr;
    void(APIENTRY *DepthMask)(GLboolean) = nullptr;
    void(APIENTRY *BlendFunc)(GLenum, GLenum) = nullptr;
    void(APIENTRY *PolygonOffset)(GLfloat, GLfloat) = nullptr;
    void(APIENTRY *LineWidth)(GLfloat) = nullptr;
    void(APIENTRY *DrawArrays)(GLenum, GLint, GLsizei) = nullptr;
    void(APIENTRY *DrawElements)(GLenum, GLsizei, GLenum, const void *) = nullptr;
    void(APIENTRY *ReadPixels)(GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, void *) = nullptr;

    void(APIENTRY *GenTextures)(GLsizei, GLuint *) = nullptr;
    void(APIENTRY *DeleteTextures)(GLsizei, const GLuint *) = nullptr;
    void(APIENTRY *BindTexture)(GLenum, GLuint) = nullptr;
    void(APIENTRY *TexImage2D)(GLenum, GLint, GLint, GLsizei, GLsizei, GLint, GLenum, GLenum, const void *) = nullptr;
    void(APIENTRY *TexParameteri)(GLenum, GLenum, GLint) = nullptr;

    void(APIENTRY *GenFramebuffers)(GLsizei, GLuint *) = nullptr;
    void(APIENTRY *DeleteFramebuffers)(GLsizei, const GLuint *) = nullptr;
    void(APIENTRY *BindFramebuffer)(GLenum, GLuint) = nullptr;
    void(APIENTRY *FramebufferTexture2D)(GLenum, GLenum, GLenum, GLuint, GLint) = nullptr;
    void(APIENTRY *GenRenderbuffers)(GLsizei, GLuint *) = nullptr;
    void(APIENTRY *DeleteRenderbuffers)(GLsizei, const GLuint *) = nullptr;
    void(APIENTRY *BindRenderbuffer)(GLenum, GLuint) = nullptr;
    void(APIENTRY *RenderbufferStorage)(GLenum, GLenum, GLsizei, GLsizei) = nullptr;
    void(APIENTRY *FramebufferRenderbuffer)(GLenum, GLenum, GLenum, GLuint) = nullptr;
    GLenum(APIENTRY *CheckFramebufferStatus)(GLenum) = nullptr;

    void(APIENTRY *GenVertexArrays)(GLsizei, GLuint *) = nullptr;
    void(APIENTRY *DeleteVertexArrays)(GLsizei, const GLuint *) = nullptr;
    void(APIENTRY *BindVertexArray)(GLuint) = nullptr;
    void(APIENTRY *GenBuffers)(GLsizei, GLuint *) = nullptr;
    void(APIENTRY *DeleteBuffers)(GLsizei, const GLuint *) = nullptr;
    void(APIENTRY *BindBuffer)(GLenum, GLuint) = nullptr;
    void(APIENTRY *BufferData)(GLenum, GLsizeiptr, const void *, GLenum) = nullptr;
    void(APIENTRY *VertexAttribPointer)(GLuint, GLint, GLenum, GLboolean, GLsizei, const void *) = nullptr;
    void(APIENTRY *EnableVertexAttribArray)(GLuint) = nullptr;

    GLuint(APIENTRY *CreateShader)(GLenum) = nullptr;
    void(APIENTRY *DeleteShader)(GLuint) = nullptr;
    void(APIENTRY *ShaderSource)(GLuint, GLsizei, const GLchar *const *, const GLint *) = nullptr;
    void(APIENTRY *CompileShader)(GLuint) = nullptr;
    void(APIENTRY *GetShaderiv)(GLuint, GLenum, GLint *) = nullptr;
    void(APIENTRY *GetShaderInfoLog)(GLuint, GLsizei, GLsizei *, GLchar *) = nullptr;

    GLuint(APIENTRY *CreateProgram)() = nullptr;
    void(APIENTRY *DeleteProgram)(GLuint) = nullptr;
    void(APIENTRY *AttachShader)(GLuint, GLuint) = nullptr;
    void(APIENTRY *LinkProgram)(GLuint) = nullptr;
    void(APIENTRY *GetProgramiv)(GLuint, GLenum, GLint *) = nullptr;
    void(APIENTRY *GetProgramInfoLog)(GLuint, GLsizei, GLsizei *, GLchar *) = nullptr;
    void(APIENTRY *UseProgram)(GLuint) = nullptr;
    GLint(APIENTRY *GetUniformLocation)(GLuint, const GLchar *) = nullptr;
    void(APIENTRY *UniformMatrix4fv)(GLint, GLsizei, GLboolean, const GLfloat *) = nullptr;
    void(APIENTRY *Uniform3fv)(GLint, GLsizei, const GLfloat *) = nullptr;
    void(APIENTRY *Uniform1f)(GLint, GLfloat) = nullptr;
    void(APIENTRY *Uniform1i)(GLint, GLint) = nullptr;

    bool load() {
        auto get = [](const char *name) -> void * {
            return reinterpret_cast<void *>(glfwGetProcAddress(name));
        };
        Viewport = reinterpret_cast<decltype(Viewport)>(get("glViewport"));
        Scissor = reinterpret_cast<decltype(Scissor)>(get("glScissor"));
        ClearColor = reinterpret_cast<decltype(ClearColor)>(get("glClearColor"));
        Clear = reinterpret_cast<decltype(Clear)>(get("glClear"));
        Enable = reinterpret_cast<decltype(Enable)>(get("glEnable"));
        Disable = reinterpret_cast<decltype(Disable)>(get("glDisable"));
        DepthFunc = reinterpret_cast<decltype(DepthFunc)>(get("glDepthFunc"));
        DepthMask = reinterpret_cast<decltype(DepthMask)>(get("glDepthMask"));
        BlendFunc = reinterpret_cast<decltype(BlendFunc)>(get("glBlendFunc"));
        PolygonOffset = reinterpret_cast<decltype(PolygonOffset)>(get("glPolygonOffset"));
        LineWidth = reinterpret_cast<decltype(LineWidth)>(get("glLineWidth"));
        DrawArrays = reinterpret_cast<decltype(DrawArrays)>(get("glDrawArrays"));
        DrawElements = reinterpret_cast<decltype(DrawElements)>(get("glDrawElements"));
        ReadPixels = reinterpret_cast<decltype(ReadPixels)>(get("glReadPixels"));
        GenTextures = reinterpret_cast<decltype(GenTextures)>(get("glGenTextures"));
        DeleteTextures = reinterpret_cast<decltype(DeleteTextures)>(get("glDeleteTextures"));
        BindTexture = reinterpret_cast<decltype(BindTexture)>(get("glBindTexture"));
        TexImage2D = reinterpret_cast<decltype(TexImage2D)>(get("glTexImage2D"));
        TexParameteri = reinterpret_cast<decltype(TexParameteri)>(get("glTexParameteri"));
        GenFramebuffers = reinterpret_cast<decltype(GenFramebuffers)>(get("glGenFramebuffers"));
        DeleteFramebuffers = reinterpret_cast<decltype(DeleteFramebuffers)>(get("glDeleteFramebuffers"));
        BindFramebuffer = reinterpret_cast<decltype(BindFramebuffer)>(get("glBindFramebuffer"));
        FramebufferTexture2D = reinterpret_cast<decltype(FramebufferTexture2D)>(get("glFramebufferTexture2D"));
        GenRenderbuffers = reinterpret_cast<decltype(GenRenderbuffers)>(get("glGenRenderbuffers"));
        DeleteRenderbuffers = reinterpret_cast<decltype(DeleteRenderbuffers)>(get("glDeleteRenderbuffers"));
        BindRenderbuffer = reinterpret_cast<decltype(BindRenderbuffer)>(get("glBindRenderbuffer"));
        RenderbufferStorage = reinterpret_cast<decltype(RenderbufferStorage)>(get("glRenderbufferStorage"));
        FramebufferRenderbuffer = reinterpret_cast<decltype(FramebufferRenderbuffer)>(get("glFramebufferRenderbuffer"));
        CheckFramebufferStatus = reinterpret_cast<decltype(CheckFramebufferStatus)>(get("glCheckFramebufferStatus"));
        GenVertexArrays = reinterpret_cast<decltype(GenVertexArrays)>(get("glGenVertexArrays"));
        DeleteVertexArrays = reinterpret_cast<decltype(DeleteVertexArrays)>(get("glDeleteVertexArrays"));
        BindVertexArray = reinterpret_cast<decltype(BindVertexArray)>(get("glBindVertexArray"));
        GenBuffers = reinterpret_cast<decltype(GenBuffers)>(get("glGenBuffers"));
        DeleteBuffers = reinterpret_cast<decltype(DeleteBuffers)>(get("glDeleteBuffers"));
        BindBuffer = reinterpret_cast<decltype(BindBuffer)>(get("glBindBuffer"));
        BufferData = reinterpret_cast<decltype(BufferData)>(get("glBufferData"));
        VertexAttribPointer = reinterpret_cast<decltype(VertexAttribPointer)>(get("glVertexAttribPointer"));
        EnableVertexAttribArray = reinterpret_cast<decltype(EnableVertexAttribArray)>(get("glEnableVertexAttribArray"));
        CreateShader = reinterpret_cast<decltype(CreateShader)>(get("glCreateShader"));
        DeleteShader = reinterpret_cast<decltype(DeleteShader)>(get("glDeleteShader"));
        ShaderSource = reinterpret_cast<decltype(ShaderSource)>(get("glShaderSource"));
        CompileShader = reinterpret_cast<decltype(CompileShader)>(get("glCompileShader"));
        GetShaderiv = reinterpret_cast<decltype(GetShaderiv)>(get("glGetShaderiv"));
        GetShaderInfoLog = reinterpret_cast<decltype(GetShaderInfoLog)>(get("glGetShaderInfoLog"));
        CreateProgram = reinterpret_cast<decltype(CreateProgram)>(get("glCreateProgram"));
        DeleteProgram = reinterpret_cast<decltype(DeleteProgram)>(get("glDeleteProgram"));
        AttachShader = reinterpret_cast<decltype(AttachShader)>(get("glAttachShader"));
        LinkProgram = reinterpret_cast<decltype(LinkProgram)>(get("glLinkProgram"));
        GetProgramiv = reinterpret_cast<decltype(GetProgramiv)>(get("glGetProgramiv"));
        GetProgramInfoLog = reinterpret_cast<decltype(GetProgramInfoLog)>(get("glGetProgramInfoLog"));
        UseProgram = reinterpret_cast<decltype(UseProgram)>(get("glUseProgram"));
        GetUniformLocation = reinterpret_cast<decltype(GetUniformLocation)>(get("glGetUniformLocation"));
        UniformMatrix4fv = reinterpret_cast<decltype(UniformMatrix4fv)>(get("glUniformMatrix4fv"));
        Uniform3fv = reinterpret_cast<decltype(Uniform3fv)>(get("glUniform3fv"));
        Uniform1f = reinterpret_cast<decltype(Uniform1f)>(get("glUniform1f"));
        Uniform1i = reinterpret_cast<decltype(Uniform1i)>(get("glUniform1i"));
        return Viewport && CreateShader && GenVertexArrays && GenFramebuffers && ReadPixels;
    }
};

} // namespace gl33
