// Disposable Windows-only research harness. Never used by application dragging.
// Compile with the installed .NET Framework csc; see POST_0.2.1_RELEASE_CANDIDATE.md.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;
using System.Windows.Forms;
using DataObject = System.Runtime.InteropServices.ComTypes.IDataObject;

[ComImport, Guid("43826d1e-e718-42ee-bc55-a1e261c37bfe"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IShellItem {
    void BindToHandler(IntPtr context, ref Guid handler, ref Guid iid, [MarshalAs(UnmanagedType.Interface)] out object result);
    void GetParent(out IShellItem parent);
    void GetDisplayName(uint flags, out IntPtr name);
    void GetAttributes(uint mask, out uint attributes);
    void Compare(IShellItem other, uint hint, out int order);
}
[ComImport, Guid("00000122-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IDropTarget {
    [PreserveSig] int DragEnter(DataObject data, uint keys, long point, ref uint effect);
    [PreserveSig] int DragOver(uint keys, long point, ref uint effect);
    [PreserveSig] int DragLeave();
    [PreserveSig] int Drop(DataObject data, uint keys, long point, ref uint effect);
}
[ComVisible(true), Guid("00000121-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IDropSource {
    [PreserveSig] int QueryContinueDrag([MarshalAs(UnmanagedType.Bool)] bool escape, uint keys);
    [PreserveSig] int GiveFeedback(uint effect);
}
[ComVisible(true), ClassInterface(ClassInterfaceType.None)]
class DragSource : IDropSource {
    public int QueryContinueDrag(bool escape, uint keys) {
        if (escape) { Probe.Log("escape"); return 0x40101; }
        if ((keys & 1) == 0) { Probe.Log("button-released"); return 0x40100; }
        return 0;
    }
    public int GiveFeedback(uint effect) { return 0x40102; }
}
[ComVisible(true), ClassInterface(ClassInterfaceType.None)]
class Formats : IEnumFORMATETC {
    FORMATETC[] formats; int index;
    public Formats(FORMATETC[] values, int start=0) { formats=values;index=start; }
    public int Next(int count, FORMATETC[] values, int[] fetched) {
        int n=0;while (n<count && index<formats.Length) values[n++]=formats[index++];
        if (fetched!=null) fetched[0]=n;return n==count?0:1;
    }
    public int Skip(int count) { index+=count;return index<=formats.Length?0:1; }
    public int Reset() { index=0;return 0; }
    public void Clone(out IEnumFORMATETC result) { result=new Formats(formats,index); }
}
[ComVisible(true), ClassInterface(ClassInterfaceType.None)]
class Files : DataObject {
    byte[] bytes;
    FORMATETC format = new FORMATETC { cfFormat=15,dwAspect=DVASPECT.DVASPECT_CONTENT,lindex=-1,tymed=TYMED.TYMED_HGLOBAL };
    public Files(string path) {
        byte[] names=Encoding.Unicode.GetBytes(path+"\0\0");bytes=new byte[20+names.Length];
        Array.Copy(BitConverter.GetBytes(20),bytes,4);bytes[16]=1;Array.Copy(names,0,bytes,20,names.Length);
    }
    public int QueryGetData(ref FORMATETC f) { return f.cfFormat==15 && (f.tymed & TYMED.TYMED_HGLOBAL)!=0?0:unchecked((int)0x80040064); }
    public void GetData(ref FORMATETC f,out STGMEDIUM medium) {
        Marshal.ThrowExceptionForHR(QueryGetData(ref f));
        IntPtr memory=Probe.GlobalAlloc(0x42,(UIntPtr)bytes.Length),ptr=Probe.GlobalLock(memory);
        Marshal.Copy(bytes,0,ptr,bytes.Length);Probe.GlobalUnlock(memory);
        medium=new STGMEDIUM { tymed=TYMED.TYMED_HGLOBAL,unionmember=memory,pUnkForRelease=null };
        Probe.Log("GetData CF_HDROP");
    }
    public void SetData(ref FORMATETC f, ref STGMEDIUM medium, bool release) {
        string name=Probe.FormatName((ushort)f.cfFormat),value="unsupported-medium";
        if (medium.tymed==TYMED.TYMED_HGLOBAL) {
            int size=(int)Probe.GlobalSize(medium.unionmember);IntPtr p=Probe.GlobalLock(medium.unionmember);
            try {
                if (name=="TargetCLSID" && size>=16) { byte[] id=new byte[16];Marshal.Copy(p,id,0,16);value=new Guid(id).ToString(); }
                else if (size>=4) value=Marshal.ReadInt32(p).ToString();
            } finally { Probe.GlobalUnlock(medium.unionmember); }
        }
        Probe.Log("SetData "+name+" = "+value+" release="+release);
        if (release) Probe.ReleaseStgMedium(ref medium);
    }
    public IEnumFORMATETC EnumFormatEtc(DATADIR direction) { return new Formats(direction==DATADIR.DATADIR_GET?new[]{format}:new FORMATETC[0]); }
    public int GetCanonicalFormatEtc(ref FORMATETC input,out FORMATETC output) { output=input;output.ptd=IntPtr.Zero;return 0x40130; }
    public void GetDataHere(ref FORMATETC f,ref STGMEDIUM s) { throw new COMException("Not implemented",unchecked((int)0x80004001)); }
    public int DAdvise(ref FORMATETC f,ADVF a,IAdviseSink sink,out int connection) { connection=0;return unchecked((int)0x80040003); }
    public void DUnadvise(int connection) { }
    public int EnumDAdvise(out IEnumSTATDATA result) { result=null;return unchecked((int)0x80040003); }
}
class Probe {
    static string log;static Stopwatch clock=Stopwatch.StartNew();
    public static void Log(string message) { File.AppendAllText(log,clock.ElapsedMilliseconds+" "+message+Environment.NewLine); }
    [DllImport("kernel32.dll")] public static extern IntPtr GlobalAlloc(uint flags, UIntPtr size);
    [DllImport("kernel32.dll")] public static extern IntPtr GlobalLock(IntPtr memory);
    [DllImport("kernel32.dll")] public static extern bool GlobalUnlock(IntPtr memory);
    [DllImport("kernel32.dll")] public static extern UIntPtr GlobalSize(IntPtr memory);
    [DllImport("ole32.dll")] public static extern void ReleaseStgMedium(ref STGMEDIUM medium);
    [DllImport("ole32.dll")] static extern int DoDragDrop(DataObject data, IDropSource source,uint effects,out uint result);
    [DllImport("shell32.dll",CharSet=CharSet.Unicode,PreserveSig=false)] static extern void SHCreateItemFromParsingName(string path,IntPtr context,ref Guid iid,out IShellItem item);
    [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetClipboardFormatName(uint id,StringBuilder name,int count);
    public static string FormatName(uint id) { var name=new StringBuilder(128);GetClipboardFormatName(id,name,name.Capacity);return name.Length==0?id.ToString():name.ToString(); }
    [STAThread] static void Main(string[] args) {
        // No arbitrary user input paths: each run creates its own expendable file.
        string root=Path.GetFullPath(args[0]);
        if (Directory.Exists(root) && Directory.GetFileSystemEntries(root).Length!=0)
            throw new InvalidOperationException("Choose a fresh, empty probe directory.");
        Directory.CreateDirectory(root);log=Path.Combine(root,"events.txt");
        string managed=Path.Combine(root,"managed.txt"),copy=Path.Combine(root,"export-"+Guid.NewGuid()+".txt");
        File.WriteAllText(managed,"Generated G27 probe, no user content");File.Copy(managed,copy);
        Log("start CF_HDROP-only export="+Path.GetFileName(copy));
        Application.OleRequired();
        var data=new Files(copy);
        if (args.Length>1 && args[1].StartsWith("shell")) {
            Guid iid=typeof(IShellItem).GUID;IShellItem item;
            string destination=Path.Combine(root,"folder");Directory.CreateDirectory(destination);
            string targetName=args[1]=="shell-folder"?destination:"::{645FF040-5081-101B-9F08-00AA002F954E}";
            SHCreateItemFromParsingName(targetName,IntPtr.Zero,ref iid,out item);
            Guid handler=new Guid("3981E225-F559-11D3-8E3A-00C04F6837D5"),targetId=typeof(IDropTarget).GUID;object target;
            item.BindToHandler(IntPtr.Zero,ref handler,ref targetId,out target);
            var drop=(IDropTarget)target;uint effect=3;
            Log("before DragEnter");Log("DragEnter hr="+drop.DragEnter(data,1,0,ref effect)+" effect="+effect);
            if (args[1]=="shell-leave") Log("DragLeave hr="+drop.DragLeave());
            else { Log("before Drop");Log("Drop hr="+drop.Drop(data,0,0,ref effect)+" effect="+effect); }
            Marshal.ReleaseComObject(target);Marshal.ReleaseComObject(item);
            Log("end managed="+File.Exists(managed)+" export="+File.Exists(copy));return;
        }
        var form=new Form { Text="G27 disposable native OLE probe",Width=480,Height=190,StartPosition=FormStartPosition.CenterScreen };
        var label=new Label { Text="Drag this generated copy to an actual Shell target. Esc cancels.",Dock=DockStyle.Fill,TextAlign=System.Drawing.ContentAlignment.MiddleCenter };
        form.Controls.Add(label);
        label.MouseDown+=(s,e)=> {
            if (e.Button!=MouseButtons.Left) return;
            Log("before DoDragDrop");uint effect;int hr=DoDragDrop(data,new DragSource(),3,out effect);
            Log("after DoDragDrop hr="+hr+" effect="+effect+" managed="+File.Exists(managed)+" export="+File.Exists(copy));
        };
        form.Shown+=(s,e)=>File.WriteAllText(Path.Combine(root,"hwnd.txt"),form.Handle.ToInt64().ToString());
        Application.Run(form);Log("window closed");
    }
}
