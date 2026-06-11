from __future__ import annotations

from core.domain.project import FileInfo
from features.chunking._c_source_splitter import split_c_source
from features.chunking._h_source_splitter import split_h_source
from features.chunking._source_text_templates import build_c_source_text, build_h_source_text

MDLSTART_FIXTURE = """\
#define Ts_sys (real_T) *mxGetPr(ssGetSFcnParam(S,0))

static void mdlStart(SimStruct *S) {
    Tsw = 1.0/fsw;
    Kpv = 100;
    Kpi = 500;
    pid_V.Kp = Kpv;
    pid_V.Ki = Kpi;
    pid_V.OutMax = 90;
}"""

MDLOUTPUTS_FIXTURE = """\
static void mdlOutputs(SimStruct *S, int_T tid) {
    if (fmod(time, Tsw) > Phase/360*Tsw && fmod(time, Tsw) < (Phase/360*Tsw + 0.5*Tsw)) {
        S1 = 1;
    }
}"""

PID_H_FIXTURE = """\
typedef struct {
    float Ref; float Fdb; float Err; float Kp; float Ki;
    float OutMax; float OutMin; float Out;
    void (*calc)();
} PID;
void pid_calc(PID *v) {
    v->Err = v->Ref - v->Fdb;
    v->Up = v->Kp * v->Err;
}"""


def test_c_chunk_mdlstart_source_text_contains_outmax_90() -> None:
    section = next(
        section for section in split_c_source(MDLSTART_FIXTURE) if section.title == "mdlStart"
    )

    source_text = build_c_source_text(FileInfo("DAB_Sfcn.c", ".c", 1), section)

    assert "OutMax" in source_text
    assert "90" in source_text


def test_c_chunk_mdloutputs_source_text_contains_phase_formula() -> None:
    section = split_c_source(MDLOUTPUTS_FIXTURE)[0]

    source_text = build_c_source_text(FileInfo("DAB_Sfcn.c", ".c", 1), section)

    assert "Phase" in source_text
    assert "360" in source_text
    assert "Tsw" in source_text


def test_h_chunk_pid_h_source_text_contains_pid_calc_signature() -> None:
    section = split_h_source(PID_H_FIXTURE)[0]

    source_text = build_h_source_text(FileInfo("PID.h", ".h", 1), section)

    assert "pid_calc" in source_text
    assert "PID *v" in source_text
