//go:build windows

package discovery

import (
	"encoding/binary"
	"fmt"
	"net"
	"syscall"
	"unsafe"
)

const (
	afInet                         = 2
	afInet6                        = 23
	tcpTableOwnerPIDAll            = 5
	errorInsufficientBuffer        = 122
	noError                        = 0
	tcpStateEstablished            = 5
	processQueryLimitedInformation = 0x1000
)

var (
	ipHelperAPI                = syscall.NewLazyDLL("iphlpapi.dll")
	getExtendedTCPTable        = ipHelperAPI.NewProc("GetExtendedTcpTable")
	kernel32                   = syscall.NewLazyDLL("kernel32.dll")
	openProcess                = kernel32.NewProc("OpenProcess")
	queryFullProcessImageNameW = kernel32.NewProc("QueryFullProcessImageNameW")
	closeHandle                = kernel32.NewProc("CloseHandle")
)

func listTCPConnections() ([]TCPConnection, error) {
	connections4, err4 := readTCPTable(afInet)
	connections6, err6 := readTCPTable(afInet6)
	if err4 != nil && err6 != nil {
		return nil, fmt.Errorf("IPv4: %v; IPv6: %v", err4, err6)
	}
	return append(connections4, connections6...), nil
}

func readTCPTable(addressFamily uintptr) ([]TCPConnection, error) {
	var size uint32
	result, _, _ := getExtendedTCPTable.Call(
		0,
		uintptr(unsafe.Pointer(&size)),
		0,
		addressFamily,
		tcpTableOwnerPIDAll,
		0,
	)
	if result != errorInsufficientBuffer && result != noError {
		return nil, syscall.Errno(result)
	}
	if size < 4 {
		return []TCPConnection{}, nil
	}

	buffer := make([]byte, size)
	result, _, _ = getExtendedTCPTable.Call(
		uintptr(unsafe.Pointer(&buffer[0])),
		uintptr(unsafe.Pointer(&size)),
		0,
		addressFamily,
		tcpTableOwnerPIDAll,
		0,
	)
	if result != noError {
		return nil, syscall.Errno(result)
	}

	rowCount := int(binary.LittleEndian.Uint32(buffer[:4]))
	processPaths := make(map[int]string)
	connections := make([]TCPConnection, 0, rowCount)
	if addressFamily == afInet {
		const rowSize = 24
		for index := 0; index < rowCount; index++ {
			offset := 4 + index*rowSize
			if offset+rowSize > len(buffer) {
				break
			}
			row := buffer[offset : offset+rowSize]
			if binary.LittleEndian.Uint32(row[0:4]) != tcpStateEstablished {
				continue
			}
			pid := int(binary.LittleEndian.Uint32(row[20:24]))
			connections = append(connections, TCPConnection{
				LocalIP:    ipv4String(binary.LittleEndian.Uint32(row[4:8])),
				LocalPort:  windowsPort(binary.LittleEndian.Uint32(row[8:12])),
				RemoteIP:   ipv4String(binary.LittleEndian.Uint32(row[12:16])),
				RemotePort: windowsPort(binary.LittleEndian.Uint32(row[16:20])),
				PID:        pid,
				Executable: cachedProcessPath(pid, processPaths),
			})
		}
		return connections, nil
	}

	const rowSize = 56
	for index := 0; index < rowCount; index++ {
		offset := 4 + index*rowSize
		if offset+rowSize > len(buffer) {
			break
		}
		row := buffer[offset : offset+rowSize]
		if binary.LittleEndian.Uint32(row[48:52]) != tcpStateEstablished {
			continue
		}
		pid := int(binary.LittleEndian.Uint32(row[52:56]))
		connections = append(connections, TCPConnection{
			LocalIP:    net.IP(row[0:16]).String(),
			LocalPort:  windowsPort(binary.LittleEndian.Uint32(row[20:24])),
			RemoteIP:   net.IP(row[24:40]).String(),
			RemotePort: windowsPort(binary.LittleEndian.Uint32(row[44:48])),
			PID:        pid,
			Executable: cachedProcessPath(pid, processPaths),
		})
	}
	return connections, nil
}

func cachedProcessPath(pid int, cache map[int]string) string {
	if path, exists := cache[pid]; exists {
		return path
	}
	path := processImagePath(pid)
	cache[pid] = path
	return path
}

func processImagePath(pid int) string {
	handle, _, _ := openProcess.Call(processQueryLimitedInformation, 0, uintptr(pid))
	if handle == 0 {
		return ""
	}
	defer closeHandle.Call(handle)

	buffer := make([]uint16, 32768)
	size := uint32(len(buffer))
	result, _, _ := queryFullProcessImageNameW.Call(
		handle,
		0,
		uintptr(unsafe.Pointer(&buffer[0])),
		uintptr(unsafe.Pointer(&size)),
	)
	if result == 0 {
		return ""
	}
	return syscall.UTF16ToString(buffer[:size])
}

func ipv4String(address uint32) string {
	return net.IPv4(byte(address), byte(address>>8), byte(address>>16), byte(address>>24)).String()
}

func windowsPort(value uint32) int {
	port := uint16(value & 0xffff)
	return int(port>>8 | port<<8)
}
