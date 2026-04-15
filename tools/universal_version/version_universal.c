/*
 * Universal version.so for iCopy-X.
 *
 * This module serves two roles with a single binary:
 *
 * 1. JAILBREAK (loaded by checkVer via ExtensionFileLoader):
 *    The running device already has "version" in sys.modules with the
 *    real SERIAL_NUMBER.  We mirror it — checkVer comparison passes.
 *
 * 2. RUNTIME (loaded at boot as the primary version module):
 *    No prior "version" in sys.modules.  We fall back to scanning
 *    backup version.so binaries on disk for the real SN, identical
 *    to what version_universal.py does.
 *
 * Build:
 *   arm-linux-gnueabihf-gcc -shared -fPIC -O2 \
 *     -I/mnt/sdcard/root2/root/usr/local/python-3.8.0/include/python3.8 \
 *     -o version.so version_universal.c
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>

/* Fallback values */
static const char *FALLBACK_SN       = "00000000";
static const char *FALLBACK_VERSION  = "2.0.0";
static const char *FALLBACK_TYP      = "iCopy-XS";
static const char *FALLBACK_HW       = "1.10";
static const char *FALLBACK_PM       = "1.0.2";
static const char *FALLBACK_HMI      = "1.0";

/* Paths to scan for the real serial number (same as version_universal.py) */
static const char *SN_SCAN_PATHS[] = {
    "/home/pi/ipk_app_bak/lib/version.so",
    "/home/pi/ipk_app_main/lib/version_orig.so",
    "/home/pi/ipk_app_main/lib/version.so",
    NULL
};

/* -------------------------------------------------------------------
 * Try to read a string attribute from the running "version" module.
 * Returns a NEW reference, or NULL on failure.
 * ------------------------------------------------------------------- */
static PyObject *
get_running_attr(const char *attr_name)
{
    PyObject *sys_modules, *running_ver, *val;

    sys_modules = PySys_GetObject("modules");
    if (!sys_modules) return NULL;

    running_ver = PyDict_GetItemString(sys_modules, "version");
    if (!running_ver) return NULL;

    val = PyObject_GetAttrString(running_ver, attr_name);
    if (!val) { PyErr_Clear(); return NULL; }

    return val;
}

/* -------------------------------------------------------------------
 * Scan a binary file for an 8-10 digit numeric string that looks
 * like a serial number.  Pattern: \x00([0-9]{8,10})\x00
 * Returns a NEW reference to a PyUnicode, or NULL.
 * ------------------------------------------------------------------- */
static PyObject *
scan_binary_for_sn(const char *path)
{
    FILE *f;
    long fsize;
    unsigned char *data;
    size_t nread;
    PyObject *result = NULL;

    f = fopen(path, "rb");
    if (!f) return NULL;

    fseek(f, 0, SEEK_END);
    fsize = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (fsize <= 0 || fsize > 512 * 1024) {
        fclose(f);
        return NULL;
    }

    data = (unsigned char *)malloc((size_t)fsize);
    if (!data) { fclose(f); return NULL; }

    nread = fread(data, 1, (size_t)fsize, f);
    fclose(f);

    /* Scan for \0 followed by 8-10 ASCII digits followed by \0 */
    for (size_t i = 0; i + 10 < nread; i++) {
        if (data[i] != 0) continue;

        /* Count consecutive digits starting at i+1 */
        size_t dstart = i + 1;
        size_t dlen = 0;
        while (dstart + dlen < nread && data[dstart + dlen] >= '0'
               && data[dstart + dlen] <= '9')
            dlen++;

        if (dlen < 8 || dlen > 10) continue;
        if (dstart + dlen >= nread || data[dstart + dlen] != 0) continue;

        /* Skip "00000000" and strings starting with "000" */
        if (dlen == 8 && memcmp(data + dstart, "00000000", 8) == 0) continue;
        if (memcmp(data + dstart, "000", 3) == 0) continue;

        result = PyUnicode_FromStringAndSize((const char *)(data + dstart),
                                            (Py_ssize_t)dlen);
        break;
    }

    free(data);
    return result;
}

/* -------------------------------------------------------------------
 * Resolve SERIAL_NUMBER:
 *   1. Mirror from running "version" in sys.modules (jailbreak path)
 *   2. Scan backup .so binaries on disk (boot-time path)
 *   3. Fall back to "00000000"
 * ------------------------------------------------------------------- */
static PyObject *
resolve_serial_number(void)
{
    PyObject *val;

    /* 1. Try the running module (checkVer bypass) */
    val = get_running_attr("SERIAL_NUMBER");
    if (val && PyUnicode_Check(val)) {
        /* Got something — but is it the real SN or just another fallback? */
        const char *s = PyUnicode_AsUTF8(val);
        if (s && strcmp(s, FALLBACK_SN) != 0)
            return val;
        Py_DECREF(val);
    }

    /* 2. Scan backup binaries (same logic as version_universal.py) */
    for (const char **p = SN_SCAN_PATHS; *p; p++) {
        val = scan_binary_for_sn(*p);
        if (val) return val;
    }

    /* 3. Fallback */
    return PyUnicode_FromString(FALLBACK_SN);
}

/* -------------------------------------------------------------------
 * Helper: get a string attr from running module, or use fallback.
 * ------------------------------------------------------------------- */
static PyObject *
get_str_or_fallback(const char *attr_name, const char *fallback)
{
    PyObject *val = get_running_attr(attr_name);
    if (val && PyUnicode_Check(val))
        return val;
    Py_XDECREF(val);
    return PyUnicode_FromString(fallback);
}

/* -------------------------------------------------------------------
 * Module-level functions matching original version.so API
 * ------------------------------------------------------------------- */

static PyObject *version_getSN(PyObject *s, PyObject *a)
{ return resolve_serial_number(); }

static PyObject *version_getTYP(PyObject *s, PyObject *a)
{ return get_str_or_fallback("TYP", FALLBACK_TYP); }

static PyObject *version_getHW(PyObject *s, PyObject *a)
{ return get_str_or_fallback("HARDWARE_VER", FALLBACK_HW); }

static PyObject *version_getOS(PyObject *s, PyObject *a)
{ return get_str_or_fallback("VERSION_STR", FALLBACK_VERSION); }

static PyObject *version_getPM(PyObject *s, PyObject *a)
{ return get_str_or_fallback("PM3_VER", FALLBACK_PM); }

static PyObject *version_getHMI(PyObject *s, PyObject *a)
{ return get_str_or_fallback("HMI_VER", FALLBACK_HMI); }

static PyMethodDef version_methods[] = {
    {"getSN",  version_getSN,  METH_NOARGS, NULL},
    {"getTYP", version_getTYP, METH_NOARGS, NULL},
    {"getHW",  version_getHW,  METH_NOARGS, NULL},
    {"getOS",  version_getOS,  METH_NOARGS, NULL},
    {"getPM",  version_getPM,  METH_NOARGS, NULL},
    {"getHMI", version_getHMI, METH_NOARGS, NULL},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef version_module = {
    PyModuleDef_HEAD_INIT,
    "version", NULL, -1, version_methods
};

PyMODINIT_FUNC
PyInit_version(void)
{
    PyObject *module, *val;

    module = PyModule_Create(&version_module);
    if (!module)
        return NULL;

    /* SERIAL_NUMBER — resolved via sys.modules mirror or binary scan */
    val = resolve_serial_number();
    PyModule_AddObject(module, "SERIAL_NUMBER", val);

    val = get_str_or_fallback("VERSION_STR", FALLBACK_VERSION);
    PyModule_AddObject(module, "VERSION_STR", val);

    val = get_str_or_fallback("TYP", FALLBACK_TYP);
    PyModule_AddObject(module, "TYP", val);

    val = get_str_or_fallback("HARDWARE_VER", FALLBACK_HW);
    PyModule_AddObject(module, "HARDWARE_VER", val);

    val = get_str_or_fallback("PM3_VER", FALLBACK_PM);
    PyModule_AddObject(module, "PM3_VER", val);

    val = get_str_or_fallback("HMI_VER", FALLBACK_HMI);
    PyModule_AddObject(module, "HMI_VER", val);

    val = get_running_attr("UID");
    if (!val) val = PyUnicode_FromString("");
    PyModule_AddObject(module, "UID", val);

    val = get_running_attr("VERSION_MAJOR");
    if (!val) val = PyLong_FromLong(2);
    PyModule_AddObject(module, "VERSION_MAJOR", val);

    val = get_running_attr("VERSION_MINOR");
    if (!val) val = PyFloat_FromDouble(0.0);
    PyModule_AddObject(module, "VERSION_MINOR", val);

    return module;
}
