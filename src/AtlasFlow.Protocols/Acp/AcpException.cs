namespace AtlasFlow.Protocols.Acp;

/// <summary>Transport or protocol failure while talking to an ACP agent.</summary>
public class AcpException : Exception
{
    public AcpException() { }

    public AcpException(string message) : base(message) { }

    public AcpException(string message, Exception innerException)
        : base(message, innerException) { }
}

/// <summary>The agent answered with a JSON-RPC error object.</summary>
public sealed class AcpRemoteException : AcpException
{
    public AcpRemoteException() { }

    public AcpRemoteException(string message) : base(message) { }

    public AcpRemoteException(string message, Exception innerException)
        : base(message, innerException) { }

    public AcpRemoteException(int code, string message, string? errorData = null)
        : base($"ACP error {code}: {message}")
    {
        Code = code;
        ErrorData = errorData;
    }

    /// <summary>The JSON-RPC error code the agent returned.</summary>
    public int Code { get; }

    /// <summary>
    /// The error's <c>data</c> member, serialized, when present.
    /// </summary>
    /// <remarks>
    /// Named <c>ErrorData</c> rather than <c>Data</c> because
    /// <see cref="Exception.Data"/> already exists and means something else.
    /// </remarks>
    public string? ErrorData { get; }
}
